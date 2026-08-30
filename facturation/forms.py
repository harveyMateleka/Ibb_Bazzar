from django import forms


class JournalForm(forms.Form):
    date = forms.DateField(
        label='Journée',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'input'}),
    )
