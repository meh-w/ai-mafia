__all__ = ("BootstrapFormMixin", "SessionJoinForm", "SessionCreateForm")


import django.forms

import game.constants


class BootstrapFormMixin:
    @staticmethod
    def _apply_bootstrap_fields(form):
        for _field_name, field in form.fields.items():
            widget = field.widget
            if isinstance(widget, django.forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(
                widget,
                (django.forms.Select, django.forms.SelectMultiple),
            ):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(
                widget,
                (django.forms.Textarea, django.forms.TextInput),
            ):
                widget.attrs.setdefault("class", "form-control")


class SessionJoinForm(BootstrapFormMixin, django.forms.Form):
    code = django.forms.CharField(
        label="Код комнаты",
        max_length=50,
        help_text="Введите короткий код из ссылки ведущего",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_fields(self)


class SessionCreateForm(BootstrapFormMixin, django.forms.Form):
    max_players = django.forms.TypedChoiceField(
        label="Игроков за столом",
        coerce=int,
        choices=[
            (n, f"{n} игроков")
            for n in range(
                game.constants.MIN_LOBBY_PLAYERS,
                game.constants.MAX_LOBBY_PLAYERS + 1,
            )
        ],
        initial=game.constants.DEFAULT_LOBBY_PLAYERS,
        help_text=(
            "Игра начнётся, когда за столом будет ровно столько человек."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap_fields(self)
