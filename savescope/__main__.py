import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax

from savescope.core.diff_engine import DiffEngine
from savescope.core.schema import SchemaManager
from savescope.core.codegen import ParserGenerator
from savescope.core.editor import SaveEditor
from savescope.core.backup import BackupManager
from savescope.core.analysis import BinaryAnalysisEngine
from savescope.core.discovery import GameDiscoveryEngine
from savescope.core.educational import EducationalContentEngine

console = Console()

def cmd_diff(args):
    path_a = Path(args.file_a)
    path_b = Path(args.file_b)
    if not path_a.exists() or not path_b.exists():
        console.print("[bold red]Error:[/] One or both input files do not exist.")
        return

    result = DiffEngine.compare_files(path_a, path_b)
    console.print(Panel.fit(
        f"[bold cyan]Comparing:[/] {path_a.name} ({result.size_a} B) vs {path_b.name} ({result.size_b} B)\n"
        f"[bold yellow]Total Changed Bytes:[/] {result.total_changed_bytes}\n"
        f"[bold green]Identical:[/] {result.identical}",
        title="Diff Analysis Result"
    ))

    if not result.identical:
        table = Table(title="Heuristic Candidate Type Inferences")
        table.add_column("Offset", style="cyan", justify="right")
        table.add_column("Hex", style="dim")
        table.add_column("Inferred Type", style="magenta")
        table.add_column("Endian", style="blue")
        table.add_column("Val A", justify="right")
        table.add_column("Val B", justify="right")
        table.add_column("Delta", style="green", justify="right")
        table.add_column("Conf.", justify="center")
        table.add_column("Analysis / Reason", style="dim")

        for cand in result.candidates[:args.limit]:
            conf_color = "bold green" if cand.confidence >= 0.85 else ("yellow" if cand.confidence >= 0.70 else "red")
            table.add_row(
                str(cand.offset),
                f"0x{cand.offset:04X}",
                cand.data_type.value,
                cand.endianness.value,
                str(cand.val_a),
                str(cand.val_b),
                f"{cand.delta:+}" if isinstance(cand.delta, (int, float)) else str(cand.delta),
                f"[{conf_color}]{cand.confidence * 100:.0f}%[/]",
                cand.reason
            )
        console.print(table)

def cmd_analyze(args):
    path = Path(args.file)
    if not path.exists():
        console.print(f"[bold red]Error:[/] File {path} not found.")
        return

    data = path.read_bytes()
    entropy = BinaryAnalysisEngine.calculate_shannon_entropy(data)
    blocks = BinaryAnalysisEngine.identify_blocks(data, chunk_size=args.chunk_size)

    console.print(Panel.fit(
        f"[bold cyan]File:[/] {path.name} ({len(data)} bytes)\n"
        f"[bold yellow]Global Shannon Entropy:[/] {entropy:.4f} / 8.0000\n"
        f"[bold magenta]Assessment:[/] " + (
            "[bold red]High Entropy - Likely Compressed or Encrypted![/]" if entropy > 7.2
            else "[bold green]Structured Binary Format / Low-to-Moderate Entropy[/]"
        ),
        title="Binary File Analysis"
    ))

    table = Table(title=f"Block Structural Identification (Chunk Size: {args.chunk_size} bytes)")
    table.add_column("Offset", style="cyan", justify="right")
    table.add_column("Hex Offset", style="dim")
    table.add_column("Size", justify="right")
    table.add_column("Entropy", justify="center")
    table.add_column("Type Classification", style="bold")
    table.add_column("Description", style="dim")

    for b in blocks:
        color = {
            "ZERO_PADDING": "dim",
            "ASCII_TEXT": "cyan",
            "STRUCTURED_DATA": "green",
            "COMPRESSED_OR_ENCRYPTED": "red",
        }.get(b["type"], "white")

        table.add_row(
            str(b["offset"]),
            f"0x{b['offset']:04X}",
            f"{b['size']} B",
            f"{b['entropy']:.2f}",
            f"[{color}]{b['type']}[/]",
            b["description"],
        )
    console.print(table)

def cmd_codegen(args):
    mgr = SchemaManager()
    schema = mgr.get_schema(args.schema_name)
    if not schema:
        # Try loading direct file
        if Path(args.schema_name).exists():
            schema = mgr.load_schema_file(args.schema_name)
        else:
            console.print(f"[bold red]Error:[/] Schema '{args.schema_name}' not found.")
            return

    code = ParserGenerator.generate_code(schema)
    if args.out:
        Path(args.out).write_text(code, encoding="utf-8")
        console.print(f"[bold green]Success:[/] Generated Python parser saved to [bold cyan]{args.out}[/]")
    else:
        syntax = Syntax(code, "python", theme="monokai", line_numbers=True)
        console.print(syntax)

def cmd_discover(args):
    console.print("[bold yellow]Scanning system for installed games and save paths...[/]")
    games = GameDiscoveryEngine.scan_common_locations()
    if not games:
        console.print("[dim]No game save directories automatically detected.[/]")
        return

    table = Table(title=f"Discovered Game Saves ({len(games)} found)")
    table.add_column("Game Name", style="bold green")
    table.add_column("Save Directory", style="dim")
    table.add_column("Saves Found", justify="right", style="cyan")

    for g in games:
        table.add_row(g.name, str(g.save_dir), str(len(g.save_files)))
    console.print(table)

def cmd_edu(args):
    if not args.topic:
        table = Table(title="SaveScope Educational Knowledgebase")
        table.add_column("Topic ID", style="cyan")
        table.add_column("Title", style="bold")
        for t in EducationalContentEngine.get_topics():
            table.add_row(t["id"], t["title"])
        console.print(table)
        console.print("\n[dim]Run: python -m savescope edu --topic <id> to view guide[/]")
    else:
        content = EducationalContentEngine.get_topic_content(args.topic)
        console.print(Panel(content, title=f"Educational Guide: {args.topic}"))

def main():
    parser = argparse.ArgumentParser(
        prog="savescope",
        description="SaveScope - Game Save Reverse Engineering & Binary Analysis Toolkit"
    )
    subparsers = parser.add_subparsers(dest="command")

    # diff command
    p_diff = subparsers.add_parser("diff", help="Compare two save files and infer modified types")
    p_diff.add_argument("file_a", help="Path to original save file")
    p_diff.add_argument("file_b", help="Path to modified save file")
    p_diff.add_argument("--limit", type=int, default=15, help="Max candidates to show")

    # analyze command
    p_ana = subparsers.add_parser("analyze", help="Entropy and block structural analysis")
    p_ana.add_argument("file", help="Path to binary save file")
    p_ana.add_argument("--chunk-size", type=int, default=32, help="Block chunk size in bytes")

    # codegen command
    p_code = subparsers.add_parser("codegen", help="Generate typed Python parser from schema")
    p_code.add_argument("schema_name", help="Schema name or JSON file path")
    p_code.add_argument("-o", "--out", help="Output .py file path")

    # discover command
    subparsers.add_parser("discover", help="Scan local system for installed games and save files")

    # edu command
    p_edu = subparsers.add_parser("edu", help="Educational tutorials and binary reverse-engineering theory")
    p_edu.add_argument("--topic", help="Topic ID (endianness, diff_methodology, shannon_entropy, integers_and_floats)")

    # gui command
    subparsers.add_parser("gui", help="Launch the modern PyQt6 desktop user interface")

    args = parser.parse_args()
    if args.command == "diff":
        cmd_diff(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "codegen":
        cmd_codegen(args)
    elif args.command == "discover":
        cmd_discover(args)
    elif args.command == "edu":
        cmd_edu(args)
    elif args.command == "gui":
        from savescope.gui.app import run_gui
        run_gui()
    else:
        # Default action: launch GUI if no args or show help
        if len(sys.argv) == 1:
            from savescope.gui.app import run_gui
            run_gui()
        else:
            parser.print_help()

if __name__ == "__main__":
    main()
