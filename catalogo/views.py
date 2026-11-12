import json
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import DireccionDespachoForm, PerfilDatosForm, RegistroClienteForm
from .models import ItemPedido, Pedido, Producto


PRODUCTOS_JSON = Path(settings.BASE_DIR) / 'catalogo' / 'data' / 'productos.json'
CLAVE_CARRITO = 'carrito'
CLAVE_SUBTOTALES_CARRITO = 'carrito_subtotales'
CLAVE_DIRECCION_PERFIL = 'perfil_direccion_despacho'
CLAVE_PREFERENCIAS_PERFIL = 'perfil_preferencias'
CLAVE_HISTORIAL_OCULTO = 'perfil_historial_oculto'
PREFERENCIAS_PERFIL_PREDETERMINADAS = {
	'alertas_pedidos': True,
	'descuentos': True,
	'historial_en_sesion': False,
}


def _cargar_productos():
	with PRODUCTOS_JSON.open(encoding='utf-8') as archivo:
		return json.load(archivo)


def _guardar_productos(productos):
	with PRODUCTOS_JSON.open('w', encoding='utf-8') as archivo:
		json.dump(productos, archivo, ensure_ascii=False, indent=2)


def _es_retorno_checkout(url):
	return urlsplit(url).path in {
		reverse('procesar_compra'),
		reverse('finalizar_compra'),
	}


def _redirigir_despues_de_autenticacion(request, url):
	if not url or not url_has_allowed_host_and_scheme(
		url,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		return redirect('lista_productos')

	if _es_retorno_checkout(url):
		return redirect(f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas")

	return redirect(url)


def login_view(request):
	next_url = request.POST.get('next') or request.GET.get('next', '')
	contexto = {
		'next': next_url,
		'checkout_requiere_autenticacion': _es_retorno_checkout(next_url),
	}

	if request.user.is_authenticated:
		return _redirigir_despues_de_autenticacion(request, next_url)

	formulario = AuthenticationForm(request, data=request.POST or None)
	if request.method == 'POST' and formulario.is_valid():
		usuario = formulario.get_user()
		login(request, usuario)
		return _redirigir_despues_de_autenticacion(request, next_url)

	contexto['formulario'] = formulario
	return render(request, 'catalogo/login.html', contexto)


def registro_view(request):
	next_url = request.POST.get('next') or request.GET.get('next', '')
	contexto = {
		'next': next_url,
		'checkout_requiere_autenticacion': _es_retorno_checkout(next_url),
	}

	if request.user.is_authenticated:
		return _redirigir_despues_de_autenticacion(request, next_url)

	formulario = RegistroClienteForm(request.POST or None)
	if request.method == 'POST' and formulario.is_valid():
		usuario = formulario.save()
		login(request, usuario)
		return _redirigir_despues_de_autenticacion(request, next_url)

	contexto['formulario'] = formulario
	return render(request, 'catalogo/registro.html', contexto)


def logout_view(request):
	logout(request)
	return redirect('lista_productos')


@login_required(login_url='login')
def perfil_view(request):
	usuario = request.user
	accion = request.POST.get('accion') if request.method == 'POST' else None
	datos_iniciales = {
		'first_name': usuario.first_name,
		'last_name': usuario.last_name,
		'email': usuario.email,
	}
	formulario = PerfilDatosForm(
		request.POST if accion == 'guardar_datos' else None,
		initial=datos_iniciales,
	)
	formulario_direccion = DireccionDespachoForm(
		request.POST if accion == 'guardar_direccion' else None,
		initial=request.session.get(CLAVE_DIRECCION_PERFIL, {}),
	)
	preferencias = {
		**PREFERENCIAS_PERFIL_PREDETERMINADAS,
		**request.session.get(CLAVE_PREFERENCIAS_PERFIL, {}),
	}

	if accion == 'guardar_datos' and formulario.is_valid():
		usuario.first_name = formulario.cleaned_data['first_name']
		usuario.last_name = formulario.cleaned_data['last_name']
		usuario.email = formulario.cleaned_data['email']
		usuario.save(update_fields=['first_name', 'last_name', 'email'])
		messages.success(request, 'Tus datos personales se actualizaron correctamente.')
		return redirect(f"{reverse('perfil')}#datos-personales")

	if accion == 'guardar_direccion' and formulario_direccion.is_valid():
		request.session[CLAVE_DIRECCION_PERFIL] = formulario_direccion.cleaned_data
		messages.success(request, 'La dirección de despacho se guardó en esta sesión.')
		return redirect(f"{reverse('perfil')}#direcciones")

	if accion == 'guardar_preferencias':
		preferencias = {
			'alertas_pedidos': request.POST.get('alertas_pedidos') == 'on',
			'descuentos': request.POST.get('descuentos') == 'on',
			'historial_en_sesion': request.POST.get('historial_en_sesion') == 'on',
		}
		request.session[CLAVE_PREFERENCIAS_PERFIL] = preferencias
		messages.success(request, 'Tus preferencias se guardaron en esta sesión.')
		return redirect(f"{reverse('perfil')}#configuracion")

	if accion == 'ocultar_historial':
		request.session[CLAVE_HISTORIAL_OCULTO] = True
		messages.success(
			request,
			'El historial se ocultó durante esta sesión. Tus pedidos no se eliminaron.',
		)
		return redirect(f"{reverse('perfil')}#configuracion")

	if accion == 'mostrar_historial':
		request.session.pop(CLAVE_HISTORIAL_OCULTO, None)
		messages.success(request, 'El historial de compras vuelve a estar visible.')
		return redirect(f"{reverse('perfil')}#historial-compras")

	historial_oculto = request.session.get(CLAVE_HISTORIAL_OCULTO, False)
	pedidos = (
		Pedido.objects.none()
		if historial_oculto
		else Pedido.objects.filter(usuario=usuario).prefetch_related('items')
	)
	return render(request, 'catalogo/perfil.html', {
		'formulario': formulario,
		'formulario_direccion': formulario_direccion,
		'preferencias': preferencias,
		'historial_oculto': historial_oculto,
		'pedidos': pedidos,
		'cantidad_pedidos': pedidos.count(),
	})


def landing_page(request):
	productos_destacados = Producto.objects.filter(stock__gt=0).order_by('id')[:4]
	return render(request, 'catalogo/landing.html', {
		'productos_destacados': productos_destacados,
	})


def lista_productos(request):
	query = request.GET.get('q', '').strip()
	filtro = request.GET.get('filtro', '')
	productos = Producto.objects.all()

	if query:
		productos = productos.filter(
			Q(nombre__icontains=query) | Q(categoria__icontains=query)
		)

	if filtro == 'critico':
		productos = productos.filter(stock__lte=5).order_by('stock')
	elif filtro == 'disponibles':
		productos = productos.filter(stock__gt=0).order_by('stock')
	else:
		filtro = ''

	total_registros = productos.count()
	con_stock = productos.filter(stock__gt=0).count()
	contexto = {
		'productos': productos,
		'total_registros': total_registros,
		'con_stock': con_stock,
		'query': query,
		'filtro': filtro,
	}
	return render(request, 'catalogo/lista.html', contexto)


def reporte_stock_critico(request):
	productos = Producto.objects.filter(stock__lte=5).order_by('stock')
	return render(request, 'catalogo/reporte_stock.html', {'productos': productos})



def prueba(request):
	return HttpResponse('Vista de prueba del catalogo')


def detalle_producto(request, producto_id):
	producto = get_object_or_404(Producto, id=producto_id)
	return render(request, 'catalogo/detalle.html', {'producto': producto})


def _buscar_producto(productos, producto_id):
	return next((producto for producto in productos if producto['id'] == producto_id), None)


def _guardar_cantidad_carrito(request, producto, cantidad):
	clave_producto = str(producto.id)
	carrito = request.session.get(CLAVE_CARRITO, {})
	subtotales = request.session.get(CLAVE_SUBTOTALES_CARRITO, {})
	carrito[clave_producto] = cantidad
	subtotales[clave_producto] = producto.precio * cantidad
	request.session[CLAVE_CARRITO] = carrito
	request.session[CLAVE_SUBTOTALES_CARRITO] = subtotales


def agregar_al_carrito(request, producto_id):
	producto = get_object_or_404(Producto, id=producto_id)
	if producto.stock <= 0:
		raise Http404('Producto sin stock')

	carrito = request.session.get(CLAVE_CARRITO, {})
	cantidad_actual = int(carrito.get(str(producto_id), 0))
	_guardar_cantidad_carrito(request, producto, min(cantidad_actual + 1, producto.stock))
	return redirect('lista_productos')


def sumar_carrito(request, producto_id):
	agregar_al_carrito(request, producto_id)
	return redirect(f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas")


def restar_carrito(request, producto_id):
	carrito = request.session.get(CLAVE_CARRITO, {})
	clave_producto = str(producto_id)

	if clave_producto in carrito:
		cantidad = int(carrito[clave_producto]) - 1
		if cantidad > 0:
			producto = Producto.objects.filter(id=producto_id).first()
			if producto is not None:
				_guardar_cantidad_carrito(request, producto, cantidad)
			else:
				carrito.pop(clave_producto)
				request.session[CLAVE_CARRITO] = carrito
				subtotales = request.session.get(CLAVE_SUBTOTALES_CARRITO, {})
				subtotales.pop(clave_producto, None)
				request.session[CLAVE_SUBTOTALES_CARRITO] = subtotales
		else:
			carrito.pop(clave_producto)
			request.session[CLAVE_CARRITO] = carrito
			subtotales = request.session.get(CLAVE_SUBTOTALES_CARRITO, {})
			subtotales.pop(clave_producto, None)
			request.session[CLAVE_SUBTOTALES_CARRITO] = subtotales
	return redirect(f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas")


def actualizar_cantidad_carrito(request, producto_id):
	if request.method != 'POST':
		return redirect('lista_productos')

	producto = Producto.objects.filter(id=producto_id).first()

	try:
		cantidad = int(request.POST.get('cantidad', '0'))
	except (TypeError, ValueError):
		messages.warning(request, 'Ingresa una cantidad válida.')
		cantidad = None

	carrito = request.session.get(CLAVE_CARRITO, {})
	subtotales = request.session.get(CLAVE_SUBTOTALES_CARRITO, {})
	clave_producto = str(producto_id)

	if producto is None:
		carrito.pop(clave_producto, None)
		subtotales.pop(clave_producto, None)
		messages.warning(request, 'El producto ya no existe y se eliminó del carrito.')
	elif cantidad is not None:
		if cantidad <= 0:
			carrito.pop(clave_producto, None)
			subtotales.pop(clave_producto, None)
		else:
			if cantidad > producto.stock:
				cantidad = producto.stock
				messages.warning(
					request,
					f"La cantidad se ajustó al stock disponible ({producto.stock}).",
				)
			if cantidad <= 0:
				carrito.pop(clave_producto, None)
				subtotales.pop(clave_producto, None)
			else:
				carrito[clave_producto] = cantidad
				subtotales[clave_producto] = producto.precio * cantidad

	request.session[CLAVE_CARRITO] = carrito
	request.session[CLAVE_SUBTOTALES_CARRITO] = subtotales
	url_anterior = request.META.get('HTTP_REFERER', '')
	if not url_anterior or not url_has_allowed_host_and_scheme(
		url_anterior,
		allowed_hosts={request.get_host()},
		require_https=request.is_secure(),
	):
		url_anterior = reverse('lista_productos')

	separador = '&' if '?' in url_anterior else '?'
	return redirect(f'{url_anterior}{separador}carrito=abierto#carritoOffcanvas')


def eliminar_del_carrito(request, producto_id):
	carrito = request.session.get(CLAVE_CARRITO, {})
	clave_producto = str(producto_id)
	carrito.pop(clave_producto, None)
	request.session[CLAVE_CARRITO] = carrito
	subtotales = request.session.get(CLAVE_SUBTOTALES_CARRITO, {})
	subtotales.pop(clave_producto, None)
	request.session[CLAVE_SUBTOTALES_CARRITO] = subtotales
	return redirect(f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas")


def vaciar_carrito(request):
	request.session.pop(CLAVE_CARRITO, None)
	request.session.pop(CLAVE_SUBTOTALES_CARRITO, None)
	return redirect(f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas")


@login_required(login_url='login')
@require_POST
def procesar_compra(request):
	carrito = request.session.get(CLAVE_CARRITO, {})
	if not carrito:
		messages.warning(request, 'El carrito está vacío.')
		return redirect('lista_productos')

	with transaction.atomic():
		seleccionados = []
		ids_obsoletos = []
		for clave_producto, cantidad in carrito.items():
			try:
				id_producto = int(clave_producto)
				cantidad = int(cantidad)
			except (TypeError, ValueError):
				messages.error(request, 'El carrito contiene un producto o una cantidad inválida.')
				return redirect('lista_productos')

			producto = Producto.objects.filter(id=id_producto).first()
			if producto is None:
				ids_obsoletos.append(clave_producto)
				continue

			if cantidad <= 0:
				messages.error(request, 'La cantidad de compra debe ser mayor que cero.')
				return redirect('lista_productos')
			if producto.stock < cantidad:
				messages.warning(
					request,
					f'Stock insuficiente para {producto.nombre}. Disponible: {producto.stock}.',
				)
				return redirect('lista_productos')

			seleccionados.append((producto, cantidad))

		if ids_obsoletos:
			for id_obsoleto in ids_obsoletos:
				carrito.pop(id_obsoleto, None)
			request.session[CLAVE_CARRITO] = carrito
			subtotales = request.session.get(CLAVE_SUBTOTALES_CARRITO, {})
			for id_obsoleto in ids_obsoletos:
				subtotales.pop(id_obsoleto, None)
			request.session[CLAVE_SUBTOTALES_CARRITO] = subtotales
			messages.warning(
				request,
				'Se eliminaron del carrito productos que ya no existen. Revisa y vuelve a finalizar la compra.',
			)
			return redirect('lista_productos')

		for producto, cantidad in seleccionados:
			producto.stock = max(producto.stock - cantidad, 0)
			producto.save()

		pedido = Pedido.objects.create(
			usuario=request.user,
			total=sum(producto.precio * cantidad for producto, cantidad in seleccionados),
		)
		ItemPedido.objects.bulk_create([
			ItemPedido(
				pedido=pedido,
				producto=producto,
				nombre_producto=producto.nombre,
				precio_unitario=producto.precio,
				cantidad=cantidad,
			)
			for producto, cantidad in seleccionados
		])

	request.session.pop(CLAVE_CARRITO, None)
	request.session.pop(CLAVE_SUBTOTALES_CARRITO, None)
	messages.success(request, 'La compra se procesó correctamente.')
	return redirect('lista_productos')


@staff_member_required(login_url='lista_productos')
def editar_producto(request, producto_id):
	producto = get_object_or_404(Producto, id=producto_id)

	if request.method == 'POST':
		producto.nombre = request.POST.get('nombre', '').strip()
		producto.categoria = request.POST.get('categoria', '').strip()
		producto.precio = int(request.POST.get('precio', producto.precio))
		producto.stock = int(request.POST.get('stock', producto.stock))
		producto.imagen = request.POST.get('imagen', '').strip()
		producto.save()
		messages.success(request, 'El producto se actualizó correctamente.')
		return redirect('lista_productos')

	return render(request, 'catalogo/formulario_producto.html', {'producto': producto, 'modo': 'Editar'})


@staff_member_required(login_url='lista_productos')
def crear_producto(request):
	productos = _cargar_productos()

	if request.method == 'POST':
		producto = {
			'id': max((item['id'] for item in productos), default=0) + 1,
			'nombre': request.POST.get('nombre', '').strip(),
			'categoria': request.POST.get('categoria', '').strip(),
			'precio': int(request.POST.get('precio', 0)),
			'stock': int(request.POST.get('stock', 0)),
			'imagen': request.POST.get('imagen', '').strip(),
		}
		productos.append(producto)
		_guardar_productos(productos)
		return redirect('detalle_producto', producto_id=producto['id'])

	return render(request, 'catalogo/formulario_producto.html', {'modo': 'Crear'})


@staff_member_required(login_url='lista_productos')
@require_POST
def eliminar_producto(request, producto_id):
	producto = get_object_or_404(Producto, id=producto_id)
	producto.delete()
	messages.success(request, 'El producto se eliminó correctamente.')
	return redirect('lista_productos')