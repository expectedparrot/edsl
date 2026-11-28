"""Track model attachments through the actual Jinja render, including branch selection."""

import operator
import re
from uuid import uuid4

from ..prompts import Prompt


class _FileReference(str):
    """Carry a render-local tag through interpolation and ordinary text filters."""

    def __new__(cls, public, marker):
        ref = super().__new__(cls, public + marker)
        ref._public = public
        return ref

    def __eq__(self, other):
        return self._public == (
            other._public if isinstance(other, _FileReference) else other
        )

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return hash(self._public)

    def __len__(self):
        return len(self._public)


class FileAnswerPlaceholder(_FileReference):
    """Render a prior upload as a whole list or one selected index."""

    def __new__(cls, name, files=(), registry=None):
        sources = [(("answer", name, i), file) for i, file in enumerate(files)]
        marker = registry.mark(sources) if registry is not None else ""
        obj = super().__new__(cls, f"<see file {name}>", marker)
        obj._name = name
        obj._files = files
        obj._registry = registry
        return obj

    def __getitem__(self, index):
        public = f"<see file {self._name}[{index}]>"
        if self._registry is None:
            return public
        try:
            i = operator.index(index)
            file = self._files[i]
        except (TypeError, IndexError):
            return public
        i = i if i >= 0 else len(self._files) + i
        return _FileReference(
            public, self._registry.mark([(("answer", self._name, i), file)])
        )


class PromptFileReferences:
    """Give file values private tags that are removed before returning a public Prompt."""

    def __init__(self):
        self.nonce = None
        self.sources = {}

    def mark(self, sources):
        if self.nonce is None:
            self.nonce = uuid4().int
        tag = f"[[{self.nonce}:{len(self.sources)}]]"
        self.sources[tag] = sources
        return tag

    def scenario_reference(self, name, file):
        tag = self.mark([(("scenario", name, 0), file)])
        return _FileReference(f"<see file {name}>", tag)

    def resolve(self, prompt):
        if not self.sources:
            return prompt, {}
        # Tags are numeric so ordinary Jinja case filters preserve them. Literal
        # lookalikes in the source text cannot be mistaken for interpolations.
        pattern = re.compile("|".join(map(re.escape, self.sources)))
        selected = {}
        for token in pattern.findall(prompt.text):
            selected.update(self.sources[token])

        def public_value(value):
            if isinstance(value, str):
                return pattern.sub("", str(value))
            if isinstance(value, (list, tuple)):
                return type(value)(public_value(v) for v in value)
            if isinstance(value, dict):
                return {public_value(k): public_value(v) for k, v in value.items()}
            return value

        public = Prompt(public_value(prompt.text))
        public.captured_variables = public_value(prompt.captured_variables)
        return public, selected
