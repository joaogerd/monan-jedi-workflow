"""Read-only diagnosis of MONAN-JEDI experiments and native PBS executions.

No retries, no qsub, no changes to manifests. Designed for non-developers.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

_ERROR = re.compile(
    r"error|fatal|abort|segmentation|permission denied|cannot open|"
    r"not found|no such file|failed|out of memory|killed|MPI_ABORT|"
    r"forrtl|netcdf:|hdf5-diag|undefined symbol|libfabric",
    re.IGNORECASE,
)
_JOB = re.compile(r"^\d+(?:\.[A-Za-z0-9_.-]+)?$")
_EXIT = re.compile(r"(?m)^\s*Exit_status\s*=\s*(-?\d+)\s*$")
_JOB_STATE = re.compile(r"(?m)^\s*job_state\s*=\s*([A-Za-z])\s*$")
_JOB_PATH = re.compile(r"(?m)^\s*(Output_Path|Error_Path)\s*=\s*(.*?)\s*$")
_RULES = [
    ("library", re.compile(r"error while loading shared libraries|undefined symbol|"
                            r"lib[^\s/]+\.so[^\s]*.*not found|libfabric", re.I),
     "Bibliotecas ou ambiente MPI ausentes no job.",
     "Conferir os módulos carregados pelo PBS, LD_LIBRARY_PATH e a compatibilidade do executável com o stack."),
    ("input", re.compile(r"no such file|cannot open|file not found|missing input|"
                          r"unable to open|does not exist", re.I),
     "Um arquivo necessário pode estar ausente ou inacessível.",
     "Conferir o caminho indicado no log, a disponibilidade no filesystem dos compute nodes e as permissões."),
    ("memory", re.compile(r"out of memory|oom.kill|memory limit|cannot allocate memory", re.I),
     "O job pode ter excedido a memória disponível.",
     "Conferir mem e recursos utilizados no PBS e ajustar a configuração de recursos do experimento."),
    ("walltime", re.compile(r"walltime exceeded|walltime limit|exceeded walltime", re.I),
     "O job pode ter atingido o limite de tempo.",
     "Conferir resources_used.walltime e a fila; ajustar o walltime dentro das regras da JACI."),
    ("crash", re.compile(r"segmentation fault|sigsegv|MPI_ABORT|forrtl: severe|"
                          r"abort\s*\(", re.I),
     "O executável científico parece ter encerrado com erro.",
     "Examinar as mensagens anteriores à falha; conferir dados de entrada, MPI, número de tarefas e namelists."),
    ("permissions", re.compile(r"permission denied|read-only file system", re.I),
     "O processo não conseguiu acessar ou gravar um arquivo.",
     "Conferir permissões de leitura/escrita e diretórios de trabalho em /p."),
]


def _json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _tail(path: Path, max_bytes: int = 150_000) -> str:
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - max_bytes))
            return stream.read().decode("utf-8", errors="replace")
    except (OSError, ValueError):
        return ""


def _pbs(job_id: str) -> dict[str, Any]:
    if not _JOB.fullmatch(job_id):
        return {"job_id": job_id, "available": False, "detail": "Identificador PBS inválido."}
    try:
        result = subprocess.run(
            ["qstat", "-x", "-f", job_id],
            capture_output=True, text=True, check=False, timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"job_id": job_id, "available": False,
                "detail": f"Consulta PBS indisponível: {type(error).__name__}"}
    if result.returncode:
        return {"job_id": job_id, "available": False,
                "detail": "Histórico PBS não encontrado ou inacessível."}
    state = _JOB_STATE.search(result.stdout)
    exit_code = _EXIT.search(result.stdout)
    paths = {name.lower(): value for name, value in _JOB_PATH.findall(result.stdout)}
    resources = {}
    for name in ("resources_used.walltime", "resources_used.mem", "Resource_List.walltime",
                 "comment", "substate"):
        found = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*(.*)$", result.stdout)
        if found:
            resources[name] = found.group(1).strip()
    return {"job_id": job_id, "available": True,
            "state": state.group(1) if state else None,
            "exit_status": int(exit_code.group(1)) if exit_code else None,
            "paths": paths, "details": resources}


def _filenames(root: Path) -> list[Path]:
    # Bounded search: diagnostic may operate on a multi-cycle campaign.
    found: list[Path] = []
    for pattern in (
        "work/**/*.log", "work/**/*.stdout", "work/**/*.stderr",
        "work/**/*.o[0-9]*", "work/**/*.e[0-9]*", "work/**/*.OU", "work/**/*.ER",
        "work/**/log.*.out", "work/**/*.out",
        ".platform/**/*.log",
    ):
        for candidate in root.glob(pattern):
            if len(found) >= 200:
                break
            if candidate.is_file() and candidate not in found:
                found.append(candidate)
    return found


def diagnose(root: Path, *, task: str | None = None, query_pbs: bool = True) -> dict[str, Any]:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Diretório do experimento não existe: {root}")
    states: list[dict[str, Any]] = []
    for path in sorted(root.glob(".platform/**/state.json")):
        value = _json(path)
        if value and value.get("state") in {"failed", "invalid", "running"}:
            states.append({"path": str(path), "state": value.get("state"),
                           "run_dir": value.get("run_dir"),
                           "last_error": (value.get("attempts") or [{}])[-1].get("error"),
                           "cycle": path.parent.parent.name,
                           "operation": path.parent.name})
    reports = []
    ids: set[str] = set()
    for path in sorted(root.glob("work/**/.monan-jedi-workflow/*.json")):
        if len(reports) >= 100:
            break
        record = _json(path)
        if record is None:
            continue
        if record.get("job_id") and isinstance(record["job_id"], str):
            ids.add(record["job_id"])
        if ("missing_log_markers" in record or "missing_outputs" in record
                or record.get("valid") is False):
            if task and task.lower() not in str(path).lower():
                continue
            if (record.get("valid") is False or record.get("missing_log_markers")
                    or record.get("missing_outputs")):
                reports.append({"path": str(path), "job_id": record.get("job_id"),
                                "missing_outputs": record.get("missing_outputs", []),
                                "missing_log_markers": record.get("missing_log_markers", []),
                                "valid": record.get("valid")})
    if task:
        states = [item for item in states if task.lower() in (
            item["operation"] + " " + item["cycle"] + " " + item["path"]
        ).lower()]
        ids = {item["job_id"] for item in reports if item.get("job_id")}
    jobs = [_pbs(job) if query_pbs else {"job_id": job, "available": False,
                                         "detail": "Consulta PBS desativada."}
            for job in sorted(ids)[-12:]]
    paths = _filenames(root)
    for job in jobs:
        for raw in job.get("paths", {}).values():
            # PBS reports host:/absolute/file. Only read within the experiment.
            value = raw.split(":", 1)[-1]
            candidate = Path(value)
            try:
                candidate = candidate.resolve()
                candidate.relative_to(root)
            except (OSError, ValueError):
                continue
            if candidate.is_file() and candidate not in paths:
                paths.append(candidate)
    if task:
        paths = [p for p in paths if task.lower() in str(p).lower()]
        # The task may be an orchestration name rather than a path component;
        # avoid hiding all logs in this common case.
        if not paths:
            paths = _filenames(root)
    matches = []
    seen_messages: dict[str, dict[str, Any]] = {}
    for path in paths:
        content = _tail(path)
        for number, line in enumerate(content.splitlines(), 1):
            if _ERROR.search(line):
                message = line.strip()[:360]
                # Repeated MPI rank failures have a single root cause.
                normalized = re.sub(r"^.*?:\s*(error while loading shared libraries:)", r"\1", message, flags=re.I)
                normalized = re.sub(r"\s+", " ", normalized).strip().lower()
                if normalized in seen_messages:
                    seen_messages[normalized]["occurrences"] += 1
                    continue
                item = {"file": str(path), "tail_line": number,
                        "message": message, "occurrences": 1}
                seen_messages[normalized] = item
                matches.append(item)
                if len(matches) >= 40:
                    break
        if len(matches) >= 40:
            break
    evidence = "\n".join((item.get("message") or "") for item in matches)
    if not evidence:
        evidence = "\n".join((item.get("last_error") or "") for item in states)
    code, title, action = ("unknown", "A causa não foi identificada automaticamente.",
                          "Consultar os logs indicados e o histórico PBS. Não ressubmeter antes de verificar o job anterior.")
    for key, expression, description, recommendation in _RULES:
        if expression.search(evidence):
            code, title, action = key, description, recommendation
            break
    # A dynamic loader error is stronger evidence than a generic missing file.
    loader = re.search(
        r"error while loading shared libraries:\s*([^: ]+):\s*cannot open",
        evidence, re.I,
    )
    if loader:
        code, title, action = (
            "missing-shared-library",
            f"O executável não iniciou: biblioteca {loader.group(1)} indisponível no nó de computação.",
            "Conferir os módulos MPI/Cray e o LD_LIBRARY_PATH efetivo do job PBS; "
            "verificar a biblioteca no nó alocado antes de repetir. "
            "Não copiar bibliotecas nem criar links simbólicos para contornar a incompatibilidade.",
        )
    failed_jobs = [j for j in jobs if j.get("exit_status") not in (None, 0)]
    if failed_jobs and code == "unknown":
        code, title, action = ("pbs-failed", "O PBS registrou um job encerrado com erro.",
                               "Consultar stdout/stderr do job e o Exit_status antes de corrigir ou repetir.")
    missing = [p for report in reports for p in report["missing_outputs"]]
    if missing and code == "unknown":
        code, title, action = ("missing-output", "A etapa não produziu todos os arquivos exigidos.",
                               "Verificar o Exit_status PBS e os logs da etapa antes de revisar os nomes dos produtos.")
    status = "failure" if (failed_jobs or reports or any(s["state"] in {"failed", "invalid"} for s in states)) else ("incomplete" if states else "no-failure-found")
    return {"experiment": str(root), "status": status,
            "diagnosis": {"code": code, "summary": title, "suggestion": action,
                          "confidence": "possible" if code not in ("pbs-failed",) else "confirmed-scheduler-failure"},
            "operations": states[:30], "validation": reports[:30],
            "pbs_jobs": jobs, "log_evidence": matches,
            "next_steps": [
                "Não executar novamente o workflow antes de verificar a situação do PBS.",
                "Conferir as linhas de erro e os arquivos ausentes listados neste relatório.",
                "Após corrigir a causa, usar o mecanismo documentado de retomada, sem apagar resultados anteriores.",
            ]}


def _display(report: dict[str, Any], *, verbose: bool = False) -> None:
    """Present a short, actionable diagnosis before technical evidence."""
    diagnosis = report["diagnosis"]
    operations = [item for item in report["operations"]
                  if item["state"] in {"failed", "invalid"}]
    failed = [j for j in report["pbs_jobs"]
              if j.get("exit_status") not in (None, 0)]
    first = operations[0] if operations else None
    job = failed[0] if failed else None
    evidence = report["log_evidence"][0] if report["log_evidence"] else None

    print()
    print("MONAN-JEDI  |  Diagnóstico da execução")
    print("-" * 62)
    if report["status"] == "failure":
        target = first["operation"].replace("-", " ").upper() if first else "EXPERIMENTO"
        cycle = first["cycle"] if first else ""
        print(f"[FALHA] {target}" + (f"  |  ciclo {cycle}" if cycle else ""))
    elif report["status"] == "incomplete":
        print("[PENDENTE] Existem operações ainda não concluídas")
    else:
        print("[INFO] Nenhuma falha identificada nos registros disponíveis")

    print()
    print("CAUSA IDENTIFICADA" if diagnosis["code"] != "unknown" else "RESULTADO")
    print("  " + diagnosis["summary"])

    if job:
        print(f"  Job PBS: {job['job_id']}  |  código de saída: {job['exit_status']}")

    if evidence:
        print()
        print("EVIDÊNCIA PRINCIPAL")
        print("  " + evidence["message"])
        count = evidence.get("occurrences", 1)
        if count > 1:
            print(f"  ({count} ocorrências da mesma mensagem MPI)")
        print("  Log: " + str(Path(evidence["file"]).relative_to(
            report["experiment"]) if Path(evidence["file"]).is_relative_to(
            report["experiment"]) else evidence["file"]))

    print()
    print("AÇÃO RECOMENDADA")
    print("  " + diagnosis["suggestion"])

    if report["validation"]:
        missing = sum(len(item["missing_outputs"]) for item in report["validation"])
        if missing:
            print()
            print("CONSEQUÊNCIA")
            print(f"  {missing} arquivo(s) científico(s) esperado(s) não produzido(s).")
            if verbose:
                for item in report["validation"]:
                    for value in item["missing_outputs"]:
                        print("  - " + value)

    if verbose:
        print()
        print("DETALHES TÉCNICOS")
        print("  Experimento: " + report["experiment"])
        for item in report["operations"]:
            print(f"  Operação: {item['operation']} | {item['cycle']} | {item['state']}")
            if item.get("last_error"):
                print("    " + item["last_error"])
        for job in report["pbs_jobs"]:
            if job.get("available"):
                print(f"  PBS {job['job_id']}: state={job.get('state')} "
                      f"Exit_status={job.get('exit_status')}")
                for key, value in job.get("details", {}).items():
                    print(f"    {key}: {value}")
                for key, value in job.get("paths", {}).items():
                    print(f"    {key}: {value}")
            else:
                print(f"  PBS {job['job_id']}: {job.get('detail', 'Indisponível')}")
        for item in report["validation"]:
            print("  Relatório: " + item["path"])
            for marker in item["missing_log_markers"]:
                print("    Marcador ausente: " + marker)
        for item in report["log_evidence"][1:12]:
            print(f"  {item['file']}: {item['message']}")
    else:
        print()
        print("Detalhes adicionais: monan-jedi-workflow diagnose --verbose")
    print("-" * 62)
    print()



def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="monan-jedi-workflow diagnose",
        description="Diagnosticar falhas de experimento e PBS sem alterar arquivos.",
    )
    parser.add_argument("experiment", nargs="?", type=Path, default=Path("."),
                        help="Diretório do experimento (padrão: diretório atual)")
    parser.add_argument("--task", default=None, help="Filtrar por operação/ciclo")
    parser.add_argument("--json", action="store_true", help="Relatório estruturado em JSON")
    parser.add_argument("--verbose", action="store_true", help="Incluir logs, caminhos e detalhes PBS")
    parser.add_argument("--no-pbs", action="store_true", help="Consultar somente arquivos locais")
    args = parser.parse_args(argv)
    try:
        result = diagnose(args.experiment, task=args.task, query_pbs=not args.no_pbs)
    except (OSError, ValueError) as error:
        print(f"[ERRO] Não foi possível realizar o diagnóstico: {error}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _display(result, verbose=args.verbose)
    # A reported failed execution is not a diagnostic command failure.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
