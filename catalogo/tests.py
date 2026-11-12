from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import ItemPedido, Pedido, Producto


class HomePageTests(TestCase):
    def test_home_muestra_productos_disponibles_y_omite_productos_agotados(self):
        disponible = Producto.objects.create(
            nombre='Taladro destacado',
            categoria='Herramientas eléctricas',
            precio=27500,
            stock=3,
            imagen='https://example.com/taladro.jpg',
        )
        Producto.objects.create(
            nombre='Martillo agotado',
            categoria='Herramientas',
            precio=10000,
            stock=0,
        )

        response = self.client.get(reverse('landing_page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, disponible.nombre)
        self.assertContains(response, '$27,500')
        self.assertContains(
            response,
            reverse('detalle_producto', args=[disponible.id]),
        )
        self.assertContains(
            response,
            reverse('agregar_al_carrito', args=[disponible.id]),
        )
        self.assertNotContains(response, 'Martillo agotado')
        self.assertContains(response, 'Despacho a todo Chile')
        self.assertContains(response, 'home-page')


class ProductoAdminViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='administrador',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(self.usuario)
        self.producto = Producto.objects.create(
            nombre='Taladro',
            categoria='Herramientas',
            precio=27500,
            stock=7,
            imagen='https://example.com/taladro.jpg',
        )

    def test_editar_get_muestra_valores_de_la_base_de_datos(self):
        response = self.client.get(
            reverse('editar_producto', args=[self.producto.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="27500"')
        self.assertContains(response, 'value="7"')

    def test_editar_post_guarda_productos_en_la_base_de_datos(self):
        response = self.client.post(
            reverse('editar_producto', args=[self.producto.id]),
            {
                'nombre': 'Taladro actualizado',
                'categoria': 'Herramientas eléctricas',
                'precio': '31990',
                'stock': '4',
                'imagen': 'https://example.com/taladro-nuevo.jpg',
            },
        )

        self.assertRedirects(response, reverse('lista_productos'))
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, 'Taladro actualizado')
        self.assertEqual(self.producto.categoria, 'Herramientas eléctricas')
        self.assertEqual(self.producto.precio, 31990)
        self.assertEqual(self.producto.stock, 4)
        self.assertEqual(self.producto.imagen, 'https://example.com/taladro-nuevo.jpg')

    def test_eliminar_post_borra_producto_de_la_base_de_datos(self):
        response = self.client.post(
            reverse('eliminar_producto', args=[self.producto.id])
        )

        self.assertRedirects(response, reverse('lista_productos'))
        self.assertFalse(Producto.objects.filter(id=self.producto.id).exists())

    def test_eliminar_rechaza_peticion_get(self):
        response = self.client.get(
            reverse('eliminar_producto', args=[self.producto.id])
        )

        self.assertEqual(response.status_code, 405)

    def test_usuario_cliente_no_puede_acceder_a_vistas_administrativas(self):
        cliente = get_user_model().objects.create_user(
            username='cliente_sin_permisos',
            password='test-password',
        )
        self.client.force_login(cliente)

        rutas = (
            reverse('crear_producto'),
            reverse('editar_producto', args=[self.producto.id]),
            reverse('eliminar_producto', args=[self.producto.id]),
        )
        for ruta in rutas:
            with self.subTest(ruta=ruta):
                response = self.client.get(ruta)
                self.assertRedirects(
                    response,
                    f"{reverse('lista_productos')}?{urlencode({'next': ruta})}",
                    fetch_redirect_response=False,
                )

        self.producto.refresh_from_db()
        self.assertEqual(self.producto.nombre, 'Taladro')


class ListaProductosTemplateTests(TestCase):
    def test_catalogo_renderiza_productos_dinamicamente_con_precio_y_estado(self):
        agotado = Producto.objects.create(
            nombre='Producto dinámico agotado',
            categoria='Herramientas',
            precio=27500,
            stock=0,
        )
        disponible = Producto.objects.create(
            nombre='Producto dinámico disponible',
            categoria='Materiales',
            precio=12500,
            stock=3,
        )

        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, agotado.nombre)
        self.assertContains(response, disponible.nombre)
        self.assertContains(response, 'catalog-product-grid')
        self.assertContains(response, 'catalog-product-card')
        self.assertNotContains(response, '<table')
        self.assertContains(response, '$27,500')
        self.assertContains(response, '$12,500')
        self.assertContains(response, 'Agotado')
        self.assertContains(
            response,
            reverse('detalle_producto', args=[agotado.id]),
        )
        self.assertContains(
            response,
            reverse('agregar_al_carrito', args=[disponible.id]),
        )
        self.assertNotContains(response, 'Martillo carpintero de uña 16 oz')

    def test_filtros_de_stock_respetan_busqueda_y_muestran_estado_activo(self):
        Producto.objects.create(
            nombre='Taladro crítico',
            categoria='Herramientas',
            precio=27500,
            stock=2,
        )
        Producto.objects.create(
            nombre='Taladro disponible',
            categoria='Herramientas',
            precio=12500,
            stock=10,
        )
        Producto.objects.create(
            nombre='Martillo crítico',
            categoria='Herramientas',
            precio=5000,
            stock=1,
        )

        response = self.client.get(
            reverse('lista_productos'),
            {'q': 'Taladro', 'filtro': 'critico'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Taladro crítico')
        self.assertNotContains(response, 'Taladro disponible')
        self.assertNotContains(response, 'Martillo crítico')
        self.assertContains(response, 'aria-current="page"')
        self.assertContains(response, 'filtro=disponibles&amp;q=Taladro')

    def test_filtro_disponibles_omite_agotados_y_mantiene_catalogo_en_navbar(self):
        Producto.objects.create(
            nombre='Producto agotado para filtro',
            categoria='Herramientas',
            precio=10000,
            stock=0,
        )
        Producto.objects.create(
            nombre='Producto disponible para filtro',
            categoria='Herramientas',
            precio=10000,
            stock=2,
        )

        response = self.client.get(
            reverse('lista_productos'),
            {'filtro': 'disponibles'},
        )

        self.assertContains(response, 'Producto disponible para filtro')
        self.assertNotContains(response, 'Producto agotado para filtro')
        self.assertContains(response, '>Catálogo</a>')
        self.assertNotContains(response, '>Stock crítico</a>')

    def test_cliente_no_ve_acciones_administrativas(self):
        producto = Producto.objects.create(
            nombre='Producto solo para cliente',
            categoria='Herramientas',
            precio=10000,
            stock=3,
        )
        cliente = get_user_model().objects.create_user(
            username='cliente_catalogo',
            password='test-password',
        )
        self.client.force_login(cliente)

        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, producto.nombre)
        self.assertNotContains(response, 'Crear Producto')
        self.assertNotContains(response, 'Crear producto')
        self.assertNotContains(response, 'Editar')
        self.assertNotContains(response, 'Eliminar')

    def test_staff_ve_acciones_administrativas(self):
        producto = Producto.objects.create(
            nombre='Producto para staff',
            categoria='Herramientas',
            precio=10000,
            stock=3,
        )
        staff = get_user_model().objects.create_user(
            username='staff_catalogo',
            password='test-password',
            is_staff=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, 'Crear Producto')
        self.assertContains(response, 'Crear producto')
        self.assertContains(response, reverse('editar_producto', args=[producto.id]))
        self.assertContains(response, reverse('eliminar_producto', args=[producto.id]))


class ReporteStockCriticoTests(TestCase):
    def test_reporte_filtra_stock_critico_y_ordena_de_menor_a_mayor(self):
        Producto.objects.create(
            nombre='Stock alto',
            categoria='Herramientas',
            precio=10000,
            stock=6,
        )
        Producto.objects.create(
            nombre='Stock medio',
            categoria='Herramientas',
            precio=10000,
            stock=3,
        )
        Producto.objects.create(
            nombre='Stock agotado',
            categoria='Herramientas',
            precio=10000,
            stock=0,
        )
        Producto.objects.create(
            nombre='Límite crítico',
            categoria='Herramientas',
            precio=10000,
            stock=5,
        )

        response = self.client.get(reverse('reporte_stock'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Catálogo')
        self.assertContains(response, reverse('lista_productos'))
        self.assertNotContains(response, '>Stock crítico</a>')
        self.assertNotContains(response, 'Stock alto')
        contenidos = response.content.decode()
        self.assertLess(
            contenidos.index('Stock agotado'),
            contenidos.index('Stock medio'),
        )
        self.assertLess(
            contenidos.index('Stock medio'),
            contenidos.index('Límite crítico'),
        )


class CarritoTemplateTests(TestCase):
    def setUp(self):
        self.producto = Producto.objects.create(
            nombre='Taladro del carrito',
            categoria='Herramientas',
            precio=25000,
            stock=4,
            imagen='https://example.com/taladro.jpg',
        )

    def test_carrito_vacio_muestra_estado_y_enlace_al_catalogo(self):
        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, 'cart-drawer')
        self.assertContains(response, 'Tu carrito está vacío')
        self.assertContains(response, reverse('lista_productos'))
        self.assertNotContains(response, 'Finalizar compra')

    def test_carrito_con_productos_muestra_cantidades_total_y_checkout(self):
        session = self.client.session
        session['carrito'] = {str(self.producto.id): 2}
        session.save()

        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, self.producto.nombre)
        self.assertContains(response, 'value="2"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, reverse('sumar_carrito', args=[self.producto.id]))
        self.assertContains(response, reverse('restar_carrito', args=[self.producto.id]))
        self.assertContains(response, reverse('eliminar_del_carrito', args=[self.producto.id]))
        self.assertContains(response, 'Finalizar compra')
        self.assertContains(response, reverse('procesar_compra'))
        self.assertContains(response, '$50,000')


class AutenticacionTests(TestCase):
    def test_login_conserva_next_en_formulario_y_enlace_a_registro(self):
        next_url = reverse('procesar_compra')

        response = self.client.get(reverse('login'), {'next': next_url})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'name="next" value="{next_url}"')
        self.assertContains(
            response,
            f'href="{reverse("registro")}?next={next_url}"',
        )
        self.assertContains(response, 'Tu carrito se conservará.')

    def test_login_redirige_al_catalogo_con_carrito_abierto_y_conserva_sesion(self):
        usuario = get_user_model().objects.create_user(
            username='cliente_login',
            password='test-password',
        )
        carrito = {'1': 2}
        session = self.client.session
        session['carrito'] = carrito
        session['carrito_subtotales'] = {'1': 50000}
        session.save()

        response = self.client.post(
            reverse('login'),
            {
                'username': 'cliente_login',
                'password': 'test-password',
                'next': reverse('procesar_compra'),
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas",
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.session['carrito'], carrito)
        self.assertEqual(self.client.session['carrito_subtotales'], {'1': 50000})

    def test_registro_inicia_sesion_conserva_carrito_y_retorna_al_checkout(self):
        session = self.client.session
        session['carrito'] = {'1': 3}
        session['carrito_subtotales'] = {'1': 75000}
        session.save()

        response = self.client.post(
            reverse('registro'),
            {
                'username': 'nuevo_cliente',
                'email': 'nuevo@example.com',
                'password1': 'UnaClaveSegura-8472',
                'password2': 'UnaClaveSegura-8472',
                'next': reverse('procesar_compra'),
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('lista_productos')}?carrito=abierto#carritoOffcanvas",
            fetch_redirect_response=False,
        )
        self.assertTrue(
            get_user_model().objects.filter(username='nuevo_cliente').exists()
        )
        self.assertEqual(
            get_user_model().objects.get(username='nuevo_cliente').email,
            'nuevo@example.com',
        )
        self.assertEqual(self.client.session['carrito'], {'1': 3})
        self.assertEqual(self.client.session['carrito_subtotales'], {'1': 75000})

    def test_registro_renderiza_campos_y_ayuda_en_espanol_con_clases_bootstrap(self):
        response = self.client.get(reverse('registro'))

        self.assertContains(response, 'Correo electrónico')
        self.assertContains(response, 'Confirmar contraseña')
        self.assertContains(response, 'Usa al menos 8 caracteres')
        self.assertContains(response, 'class="form-control bg-dark text-white border-secondary"')
        self.assertNotContains(response, 'This password')

    def test_registro_rechaza_correo_ausente_y_contrasena_debil_en_espanol(self):
        response = self.client.post(
            reverse('registro'),
            {
                'username': 'cliente_sin_correo',
                'email': '',
                'password1': '12345678',
                'password2': '12345678',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ingresa tu correo electrónico.')
        self.assertContains(response, 'no puede estar formada solo por números')
        self.assertFalse(
            get_user_model().objects.filter(username='cliente_sin_correo').exists()
        )

    def test_next_externo_no_redirige_fuera_del_sitio(self):
        usuario = get_user_model().objects.create_user(
            username='cliente_next',
            password='test-password',
        )
        response = self.client.post(
            reverse('login'),
            {
                'username': 'cliente_next',
                'password': 'test-password',
                'next': 'https://example.com/externo',
            },
        )
        self.assertRedirects(
            response,
            reverse('lista_productos'),
            fetch_redirect_response=False,
        )


class ProcesarCompraTests(TestCase):
    def setUp(self):
        self.producto_con_stock = Producto.objects.create(
            nombre='Taladro',
            categoria='Herramientas',
            precio=25000,
            stock=2,
        )
        self.producto_stock_insuficiente = Producto.objects.create(
            nombre='Martillo',
            categoria='Herramientas',
            precio=10000,
            stock=1,
        )

    def _guardar_carrito(self, carrito):
        session = self.client.session
        session['carrito'] = carrito
        session['carrito_subtotales'] = {}
        session.save()

    def _iniciar_sesion(self):
        usuario = get_user_model().objects.create_user(
            username='cliente_compra',
            password='test-password',
        )
        self.client.force_login(usuario)
        return usuario

    def test_procesa_compra_y_guarda_stock_cero(self):
        usuario = self._iniciar_sesion()
        self._guardar_carrito({str(self.producto_con_stock.id): 2})

        response = self.client.post(reverse('procesar_compra'), follow=True)

        self.assertEqual(response.redirect_chain, [(reverse('lista_productos'), 302)])
        self.assertContains(response, 'La compra se procesó correctamente.')
        self.producto_con_stock.refresh_from_db()
        self.assertEqual(self.producto_con_stock.stock, 0)
        self.assertNotIn('carrito', self.client.session)
        self.assertNotIn('carrito_subtotales', self.client.session)
        self.assertTrue(Pedido.objects.filter(usuario=usuario).exists())

    def test_compra_autenticada_guarda_pedido_y_detalle_con_snapshot(self):
        usuario = get_user_model().objects.create_user(
            username='cliente',
            password='test-password',
        )
        self.client.force_login(usuario)
        self._guardar_carrito({str(self.producto_con_stock.id): 2})
        self.producto_con_stock.nombre = 'Taladro actualizado'
        self.producto_con_stock.save()

        response = self.client.post(reverse('procesar_compra'), follow=True)

        self.assertContains(response, 'La compra se procesó correctamente.')
        pedido = Pedido.objects.get(usuario=usuario)
        self.assertEqual(pedido.total, 50000)
        item = pedido.items.get()
        self.assertEqual(item.producto, self.producto_con_stock)
        self.assertEqual(item.nombre_producto, 'Taladro actualizado')
        self.assertEqual(item.precio_unitario, 25000)
        self.assertEqual(item.cantidad, 2)


    def test_stock_insuficiente_no_descuenta_ni_limpia_carrito(self):
        self._iniciar_sesion()
        carrito = {
            str(self.producto_con_stock.id): 1,
            str(self.producto_stock_insuficiente.id): 2,
        }
        self._guardar_carrito(carrito)

        response = self.client.post(reverse('procesar_compra'))

        self.assertRedirects(response, reverse('lista_productos'))
        self.producto_con_stock.refresh_from_db()
        self.producto_stock_insuficiente.refresh_from_db()
        self.assertEqual(self.producto_con_stock.stock, 2)
        self.assertEqual(self.producto_stock_insuficiente.stock, 1)
        self.assertEqual(self.client.session['carrito'], carrito)

    def test_ruta_antigua_de_finalizacion_sigue_funcionando(self):
        self._iniciar_sesion()
        self._guardar_carrito({str(self.producto_con_stock.id): 1})

        response = self.client.post(reverse('finalizar_compra'))

        self.assertRedirects(response, reverse('lista_productos'))

    def test_elimina_ids_obsoletos_sin_error_404(self):
        self._iniciar_sesion()
        carrito = {
            str(self.producto_con_stock.id): 1,
            '99999': 1,
        }
        self._guardar_carrito(carrito)

        response = self.client.post(reverse('procesar_compra'))

        self.assertRedirects(response, reverse('lista_productos'))
        self.assertEqual(self.client.session['carrito'], {str(self.producto_con_stock.id): 1})
        self.producto_con_stock.refresh_from_db()
        self.assertEqual(self.producto_con_stock.stock, 2)

    def test_checkout_requiere_post(self):
        self._iniciar_sesion()
        response = self.client.get(reverse('procesar_compra'))

        self.assertEqual(response.status_code, 405)

    def test_checkout_anónimo_redirige_a_login_con_next_y_conserva_carrito(self):
        carrito = {str(self.producto_con_stock.id): 1}
        self._guardar_carrito(carrito)

        response = self.client.post(reverse('procesar_compra'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('procesar_compra')}",
            fetch_redirect_response=False,
        )
        self.producto_con_stock.refresh_from_db()
        self.assertEqual(self.producto_con_stock.stock, 2)
        self.assertEqual(self.client.session['carrito'], carrito)

        login_response = self.client.get(response.url)
        self.assertContains(login_response, 'Tu carrito se conservará.')
        self.assertContains(
            login_response,
            f'href="{reverse("registro")}?next={reverse("procesar_compra")}"',
        )

    def test_formulario_de_checkout_incluye_post_y_csrf(self):
        self._guardar_carrito({str(self.producto_con_stock.id): 1})

        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, f'action="{reverse("procesar_compra")}"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')


class PerfilTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='cliente',
            password='test-password',
            email='anterior@example.com',
        )

    def test_perfil_requiere_autenticacion(self):
        response = self.client.get(reverse('perfil'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('perfil')}",
        )

    def test_perfil_muestra_datos_y_estado_vacio_de_compras(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('perfil'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Aún no tienes compras realizadas')
        self.assertContains(response, self.usuario.username)
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="last_name"')
        self.assertContains(response, 'name="email"')

    def test_perfil_actualiza_datos_basicos(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('perfil'),
            {
                'accion': 'guardar_datos',
                'first_name': 'Ana',
                'last_name': 'Latorre',
                'email': 'ana@example.com',
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('perfil')}#datos-personales",
            fetch_redirect_response=False,
        )
        self.usuario.refresh_from_db()
        self.assertEqual(self.usuario.first_name, 'Ana')
        self.assertEqual(self.usuario.last_name, 'Latorre')
        self.assertEqual(self.usuario.email, 'ana@example.com')

    def test_perfil_guarda_y_recupera_direccion_de_despacho_desde_sesion(self):
        self.client.force_login(self.usuario)
        direccion = {
            'accion': 'guardar_direccion',
            'nombre_receptor': 'Ana Latorre',
            'telefono': '+56912345678',
            'direccion': 'Av. Central 123',
            'comuna': 'Santiago',
            'region': 'Metropolitana',
            'codigo_postal': '8320000',
        }

        response = self.client.post(reverse('perfil'), direccion)

        self.assertRedirects(
            response,
            f"{reverse('perfil')}#direcciones",
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.session['perfil_direccion_despacho'],
            {
                'nombre_receptor': 'Ana Latorre',
                'telefono': '+56912345678',
                'direccion': 'Av. Central 123',
                'comuna': 'Santiago',
                'region': 'Metropolitana',
                'codigo_postal': '8320000',
            },
        )
        response = self.client.get(reverse('perfil'))
        self.assertContains(response, 'value="Ana Latorre"')
        self.assertContains(response, 'value="Av. Central 123"')

    def test_direccion_invalida_muestra_errores_y_no_guarda_en_sesion(self):
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('perfil'),
            {'accion': 'guardar_direccion', 'direccion': ''},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ingresa una dirección de despacho.')
        self.assertNotIn('perfil_direccion_despacho', self.client.session)

    def test_perfil_guarda_preferencias_en_sesion_y_puede_ocultar_y_restaurar_historial(self):
        self.client.force_login(self.usuario)
        pedido = Pedido.objects.create(usuario=self.usuario, total=1000)

        response = self.client.post(
            reverse('perfil'),
            {
                'accion': 'guardar_preferencias',
                'alertas_pedidos': 'on',
                'historial_en_sesion': 'on',
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('perfil')}#configuracion",
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.client.session['perfil_preferencias'],
            {
                'alertas_pedidos': True,
                'descuentos': False,
                'historial_en_sesion': True,
            },
        )

        response = self.client.post(
            reverse('perfil'),
            {'accion': 'ocultar_historial'},
            follow=True,
        )
        self.assertContains(response, 'El historial está oculto en esta sesión')
        self.assertContains(response, 'El historial se ocultó durante esta sesión.')
        self.assertFalse(response.context['pedidos'])
        self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())

        response = self.client.post(
            reverse('perfil'),
            {'accion': 'mostrar_historial'},
            follow=True,
        )
        self.assertContains(response, f'PEDIDO #{pedido.id}')
        self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())

    def test_perfil_muestra_formularios_de_direccion_configuracion_y_cambio_password(self):
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('perfil'))

        self.assertContains(response, 'name="accion" value="guardar_direccion"')
        self.assertContains(response, 'name="accion" value="guardar_preferencias"')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, reverse('password_change'))

    def test_cambiar_contrasena_requiere_autenticacion(self):
        response = self.client.get(reverse('password_change'))

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={reverse('password_change')}",
        )

    def test_usuario_puede_cambiar_contrasena_desde_su_perfil(self):
        self.usuario.set_password('Clave-anterior-8241')
        self.usuario.save()
        self.client.force_login(self.usuario)

        response = self.client.post(
            reverse('password_change'),
            {
                'old_password': 'Clave-anterior-8241',
                'new_password1': 'Clave-nueva-segura-5387',
                'new_password2': 'Clave-nueva-segura-5387',
            },
        )

        self.assertRedirects(response, reverse('perfil'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Clave-nueva-segura-5387'))

    def test_historial_muestra_solo_pedidos_del_usuario_actual(self):
        otro_usuario = get_user_model().objects.create_user(
            username='otra-cliente',
            password='test-password',
        )
        pedido_propio = Pedido.objects.create(usuario=self.usuario, total=1000)
        pedido_ajeno = Pedido.objects.create(usuario=otro_usuario, total=5000)
        producto = Producto.objects.create(
            nombre='Tornillo',
            categoria='Fijaciones',
            precio=1000,
            stock=2,
        )
        ItemPedido.objects.create(
            pedido=pedido_propio,
            producto=producto,
            nombre_producto='Tornillo',
            precio_unitario=1000,
            cantidad=1,
        )
        self.client.force_login(self.usuario)

        response = self.client.get(reverse('perfil'))

        self.assertContains(response, f'PEDIDO #{pedido_propio.id}')
        self.assertNotContains(response, f'PEDIDO #{pedido_ajeno.id}')
        self.assertContains(response, 'En preparación')
        self.assertContains(response, 'Tornillo')
