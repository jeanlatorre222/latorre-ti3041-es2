from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.core.exceptions import ValidationError


class PerfilDatosForm(forms.Form):
    first_name = forms.CharField(
        label='Nombre',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        label='Apellido',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'family-name'}),
    )
    email = forms.EmailField(
        label='Correo electrónico',
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'autocomplete': 'email'}),
    )


class DireccionDespachoForm(forms.Form):
    nombre_receptor = forms.CharField(
        label='Nombre de quien recibe',
        max_length=150,
        error_messages={'required': 'Ingresa el nombre de quien recibirá el pedido.'},
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'name',
        }),
    )
    telefono = forms.CharField(
        label='Teléfono de contacto',
        max_length=30,
        error_messages={'required': 'Ingresa un teléfono de contacto.'},
        widget=forms.TelInput(attrs={
            'class': 'form-control',
            'autocomplete': 'tel',
        }),
    )
    direccion = forms.CharField(
        label='Dirección',
        max_length=200,
        error_messages={'required': 'Ingresa una dirección de despacho.'},
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'street-address',
        }),
    )
    comuna = forms.CharField(
        label='Comuna',
        max_length=100,
        error_messages={'required': 'Ingresa la comuna.'},
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'address-level2',
        }),
    )
    region = forms.CharField(
        label='Región',
        max_length=100,
        error_messages={'required': 'Ingresa la región.'},
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'address-level1',
        }),
    )
    codigo_postal = forms.CharField(
        label='Código postal',
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'autocomplete': 'postal-code',
        }),
    )


class PerfilPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuracion = {
            'old_password': {
                'label': 'Contraseña actual',
                'autocomplete': 'current-password',
            },
            'new_password1': {
                'label': 'Nueva contraseña',
                'help_text': (
                    'Usa al menos 8 caracteres y evita contraseñas comunes o '
                    'basadas únicamente en números.'
                ),
                'autocomplete': 'new-password',
            },
            'new_password2': {
                'label': 'Confirmar nueva contraseña',
                'help_text': 'Escribe nuevamente la nueva contraseña.',
                'autocomplete': 'new-password',
            },
        }
        for nombre, opciones in configuracion.items():
            campo = self.fields[nombre]
            campo.label = opciones['label']
            campo.widget.attrs.update({
                'class': 'form-control',
                'autocomplete': opciones['autocomplete'],
            })
            if 'help_text' in opciones:
                campo.help_text = opciones['help_text']


class RegistroClienteForm(UserCreationForm):
    email = forms.EmailField(
        label='Correo electrónico',
        required=True,
        error_messages={
            'required': 'Ingresa tu correo electrónico.',
            'invalid': 'Ingresa una dirección de correo electrónico válida.',
        },
    )

    error_messages = {
        **UserCreationForm.error_messages,
        'password_mismatch': 'Las contraseñas no coinciden.',
    }

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')
        error_messages = {
            'username': {
                'unique': 'Ya existe una cuenta con ese nombre de usuario.',
                'invalid': 'El nombre de usuario contiene caracteres no permitidos.',
                'required': 'Ingresa un nombre de usuario.',
            },
        }

    mensajes_validacion_password = {
        'password_too_short': 'La contraseña debe tener al menos 8 caracteres.',
        'password_too_common': 'La contraseña es demasiado común. Elige una más segura.',
        'password_entirely_numeric': 'La contraseña no puede estar formada solo por números.',
        'password_too_similar': 'La contraseña es demasiado parecida a tu información personal.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuracion = {
            'username': {
                'label': 'Nombre de usuario',
                'help_text': (
                    'Obligatorio. Hasta 150 caracteres. Usa letras, números y '
                    'los símbolos @, ., +, - o _.'
                ),
                'autocomplete': 'username',
                'error_messages': {
                    'required': 'Ingresa un nombre de usuario.',
                },
            },
            'email': {
                'autocomplete': 'email',
            },
            'password1': {
                'label': 'Contraseña',
                'help_text': (
                    'Usa al menos 8 caracteres. No elijas una contraseña común, '
                    'solo numérica o que incluya información personal fácil de adivinar.'
                ),
                'autocomplete': 'new-password',
                'error_messages': {
                    'required': 'Ingresa una contraseña.',
                },
            },
            'password2': {
                'label': 'Confirmar contraseña',
                'help_text': 'Escribe nuevamente la contraseña para confirmarla.',
                'autocomplete': 'new-password',
                'error_messages': {
                    'required': 'Confirma tu contraseña.',
                },
            },
        }

        for nombre, opciones in configuracion.items():
            campo = self.fields[nombre]
            campo.label = opciones.get('label', campo.label)
            if 'help_text' in opciones:
                campo.help_text = opciones['help_text']
            campo.widget.attrs.update({
                'class': 'form-control bg-dark text-white border-secondary',
                'autocomplete': opciones['autocomplete'],
            })
            campo.error_messages.update(opciones.get('error_messages', {}))

    def validate_password_for_user(self, user, password_field_name='password2'):
        password = self.cleaned_data.get(password_field_name)
        if not password:
            return

        try:
            password_validation.validate_password(password, user)
        except ValidationError as error:
            errores_traducidos = [
                ValidationError(
                    self.mensajes_validacion_password.get(
                        detalle.code,
                        'La contraseña no cumple los requisitos de seguridad.',
                    ),
                    code=detalle.code,
                )
                for detalle in error.error_list
            ]
            self.add_error(password_field_name, errores_traducidos)
