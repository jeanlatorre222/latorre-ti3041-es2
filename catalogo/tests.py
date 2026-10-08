from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from .models import Producto


class ProductoAdminViewsTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username='administrador',
            password='test-password',
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

    def test_procesa_compra_y_guarda_stock_cero(self):
        self._guardar_carrito({str(self.producto_con_stock.id): 2})

        response = self.client.post(reverse('procesar_compra'), follow=True)

        self.assertEqual(response.redirect_chain, [(reverse('lista_productos'), 302)])
        self.assertContains(response, 'La compra se procesó correctamente.')
        self.producto_con_stock.refresh_from_db()
        self.assertEqual(self.producto_con_stock.stock, 0)
        self.assertNotIn('carrito', self.client.session)
        self.assertNotIn('carrito_subtotales', self.client.session)

    def test_stock_insuficiente_no_descuenta_ni_limpia_carrito(self):
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
        self._guardar_carrito({str(self.producto_con_stock.id): 1})

        response = self.client.post(reverse('finalizar_compra'))

        self.assertRedirects(response, reverse('lista_productos'))

    def test_elimina_ids_obsoletos_sin_error_404(self):
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
        response = self.client.get(reverse('procesar_compra'))

        self.assertEqual(response.status_code, 405)

    def test_formulario_de_checkout_incluye_post_y_csrf(self):
        self._guardar_carrito({str(self.producto_con_stock.id): 1})

        response = self.client.get(reverse('lista_productos'))

        self.assertContains(response, f'action="{reverse("procesar_compra")}"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
