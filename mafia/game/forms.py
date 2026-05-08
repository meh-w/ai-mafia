__all__ = (
    "BootstrapFormMixin",
    "VoteForm",
)


import django.forms

import game.models


class BootstrapFormMixin:
    @staticmethod
    def _apply_bootstrap_fields(form):
        for _name, field in form.fields.items():
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


class VoteForm(BootstrapFormMixin, django.forms.Form):
    def __init__(self, *args, session, voter, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"] = django.forms.ModelChoiceField(
            label="Голос на исключение",
            help_text="Выберите игрока, которого подозреваете больше всего.",
            queryset=game.models.Participant.objects.filter(
                session=session,
                is_alive=True,
            ).exclude(pk=voter.pk),
        )

        self._apply_bootstrap_fields(self)


def _trait_field_widget(placeholder: str) -> django.forms.TextInput:
    return django.forms.TextInput(
        attrs={
            "class": "form-control form-control-lg",
            "autocomplete": "off",
            "placeholder": placeholder,
        },
    )


class TraitPrepForm(django.forms.Form):
    habit = django.forms.CharField(
        label="Привычка",
        widget=_trait_field_widget("напр.: постоянно крутит кольцо на пальце"),
        required=True,
    )
    appearance = django.forms.CharField(
        label="Особенность внешности/одежды",
        widget=_trait_field_widget(
            "напр.: ярко-красные шнурки, пахнет табаком"
        ),
        required=True,
    )
    accessory = django.forms.CharField(
        label="Предмет при себе",
        widget=_trait_field_widget("напр.: старая зажигалка, помятый блокнот"),
        required=True,
    )
