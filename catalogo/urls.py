from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.urls import path, reverse_lazy

from . import views
from .forms import PerfilPasswordChangeForm

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('productos/', views.lista_productos, name='lista_productos'),
    path('reportes/stock-critico/', views.reporte_stock_critico, name='reporte_stock'),
    path('producto/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/sumar/<int:producto_id>/', views.sumar_carrito, name='sumar_carrito'),
    path('carrito/restar/<int:producto_id>/', views.restar_carrito, name='restar_carrito'),
    path('carrito/actualizar/<int:producto_id>/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('carrito/eliminar/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    path('carrito/vaciar/', views.vaciar_carrito, name='vaciar_carrito'),
    path('carrito/finalizar/', views.procesar_compra, name='finalizar_compra'),
    path('carrito/procesar/', views.procesar_compra, name='procesar_compra'),
    path('producto/<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),
    path('producto/<int:producto_id>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
    path('producto/crear/', views.crear_producto, name='crear_producto'),
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),
    path(
        'perfil/cambiar-contrasena/',
        login_required(
            PasswordChangeView.as_view(
                form_class=PerfilPasswordChangeForm,
                template_name='catalogo/cambiar_contrasena.html',
                success_url=reverse_lazy('perfil'),
            ),
            login_url='login',
        ),
        name='password_change',
    ),
]
