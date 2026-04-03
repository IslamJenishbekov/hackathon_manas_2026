from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


class PromptRenderer:
    def __init__(self) -> None:
        prompt_root = Path(__file__).resolve().parent.parent / "prompts"
        self._environment = Environment(
            loader=FileSystemLoader(str(prompt_root)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def render(self, template_name: str, context: dict[str, object]) -> str:
        return self._environment.get_template(template_name).render(**context)

