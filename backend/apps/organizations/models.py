from django.db import models


class Organization(models.Model):
    class Kind(models.TextChoices):
        BERAU = "berau", "Berau"
        ABL = "abl", "ABL"
        PLATFORM = "platform", "Platform"
        CUSTOMER = "customer", "Customer"
        PARTNER = "partner", "Partner"

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
