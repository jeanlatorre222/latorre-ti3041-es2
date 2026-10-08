from django.db import models

class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100)
    precio = models.IntegerField()
    stock = models.IntegerField()
    imagen = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"
