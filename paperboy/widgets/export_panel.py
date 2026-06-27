"""Export modal — write visible papers to BibTeX or CSV."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, RadioButton, RadioSet, Static

from paperboy.export import to_bibtex, to_csv
from paperboy.models import Paper


class ExportPanel(ModalScreen[None]):
    """Modal for exporting the visible paper list to BibTeX or CSV."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    def __init__(self, papers: list[Paper]) -> None:
        super().__init__()
        self._papers = papers

    def compose(self) -> ComposeResult:
        with Vertical(id="export-container"):
            yield Label("Export papers", id="export-title")
            yield Label(f"{len(self._papers)} paper(s) will be exported", classes="filter-label")
            yield RadioSet(
                RadioButton("BibTeX (.bib)", id="fmt-bibtex", value=True),
                RadioButton("CSV (.csv)", id="fmt-csv"),
                id="export-format",
            )
            yield Label("Output file", classes="filter-label")
            yield Input(
                value=str(Path.home() / "paperboy-export.bib"),
                id="export-path",
            )
            yield Static("", id="export-status")
            with Horizontal(id="export-buttons"):
                yield Button("Cancel", id="export-cancel", variant="default")
                yield Button("Export", id="export-apply", variant="primary")

    def on_mount(self) -> None:
        self.query_one("#export-path", Input).focus()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        path_input = self.query_one("#export-path", Input)
        current = path_input.value
        if event.pressed.id == "fmt-bibtex":
            path_input.value = current.replace(".csv", ".bib") if current.endswith(".csv") else current
        else:
            path_input.value = current.replace(".bib", ".csv") if current.endswith(".bib") else current

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "export-cancel":
            self.dismiss(None)
        elif event.button.id == "export-apply":
            self._do_export()

    def _do_export(self) -> None:
        radio_set = self.query_one("#export-format", RadioSet)
        use_bibtex = radio_set.pressed_index == 0
        path_str = self.query_one("#export-path", Input).value.strip()
        if not path_str:
            self.query_one("#export-status", Static).update("[red]Please enter a file path.[/red]")
            return

        path = Path(path_str).expanduser()
        try:
            content = to_bibtex(self._papers) if use_bibtex else to_csv(self._papers)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self.query_one("#export-status", Static).update(f"[green]Saved to {path}[/green]")
            self.set_timer(2.0, lambda: self.dismiss(None))
        except Exception as exc:
            self.query_one("#export-status", Static).update(f"[red]Error: {exc}[/red]")
