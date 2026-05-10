"""
Модели публичного каталога yembro.uz.

Каталог изолирован от ERP-операционки: товары здесь — это маркетинговые
карточки бренда, а не партии/остатки. Все текстовые поля переводятся через
django-modeltranslation в три языка (ru/uz/en) — фактические колонки в БД
создаются автоматически как `name_ru/name_uz/name_en` и т.д.
"""
from __future__ import annotations

from django.db import models
from mptt.models import MPTTModel, TreeForeignKey

from apps.common.models import TimestampedModel, UUIDModel


class Direction(models.TextChoices):
    """Целевое животное / стадия для корма."""

    BROILER = "broiler", "Бройлер"
    LAYER = "layer", "Несушка"
    PARENT = "parent", "Родительское стадо"
    UNIVERSAL = "universal", "Универсальный"


class SeoMixin(models.Model):
    """SEO-поля: meta_title/meta_description переводимые, og_image один на сущность."""

    meta_title = models.CharField(max_length=160, blank=True, verbose_name="SEO Title")
    meta_description = models.CharField(
        max_length=320, blank=True, verbose_name="SEO Description",
    )
    og_image = models.ImageField(
        upload_to="catalog/og/", blank=True, null=True, verbose_name="OG-картинка",
    )

    class Meta:
        abstract = True


class Brand(UUIDModel, TimestampedModel, SeoMixin):
    code = models.SlugField(
        unique=True, max_length=64, verbose_name="Технический код",
        help_text="Стабильный ключ, не меняется. Используется в URL-резолверах.",
    )
    slug = models.SlugField(max_length=160, verbose_name="URL-slug")
    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    logo = models.ImageField(
        upload_to="catalog/brands/", blank=True, null=True, verbose_name="Логотип",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    sort_order = models.IntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"

    def __str__(self) -> str:
        return self.name or self.code


class Category(UUIDModel, TimestampedModel, SeoMixin, MPTTModel):
    parent = TreeForeignKey(
        "self",
        null=True,
        blank=True,
        related_name="children",
        on_delete=models.CASCADE,
        verbose_name="Родительская категория",
    )
    code = models.SlugField(unique=True, max_length=64, verbose_name="Технический код")
    slug = models.SlugField(max_length=160, verbose_name="URL-slug")
    name = models.CharField(max_length=200, verbose_name="Название")
    description = models.TextField(blank=True, verbose_name="Описание")
    direction = models.CharField(
        max_length=16,
        choices=Direction.choices,
        default=Direction.UNIVERSAL,
        verbose_name="Направление",
    )
    image = models.ImageField(
        upload_to="catalog/categories/", blank=True, null=True, verbose_name="Изображение",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    sort_order = models.IntegerField(default=0, verbose_name="Порядок сортировки")

    class MPTTMeta:
        order_insertion_by = ["sort_order", "id"]

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self) -> str:
        return self.name or self.code


class Product(UUIDModel, TimestampedModel, SeoMixin):
    code = models.SlugField(unique=True, max_length=64, verbose_name="Технический код")
    slug = models.SlugField(max_length=160, verbose_name="URL-slug")
    name = models.CharField(max_length=200, verbose_name="Название")
    short_description = models.CharField(
        max_length=400, blank=True, verbose_name="Краткое описание",
    )
    description = models.TextField(blank=True, verbose_name="Полное описание")
    application = models.TextField(blank=True, verbose_name="Применение")
    brand = models.ForeignKey(
        Brand, on_delete=models.PROTECT, related_name="products", verbose_name="Бренд",
    )
    category = TreeForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        verbose_name="Категория",
    )
    direction = models.CharField(
        max_length=16,
        choices=Direction.choices,
        default=Direction.UNIVERSAL,
        verbose_name="Направление",
    )
    age_from_days = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Возраст от (дней)",
    )
    age_to_days = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="Возраст до (дней)",
    )
    package_kg = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Фасовка, кг",
    )
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    is_featured = models.BooleanField(default=False, verbose_name="Витринный")
    sort_order = models.IntegerField(default=0, verbose_name="Порядок сортировки")

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        indexes = [
            models.Index(fields=["is_active", "direction"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["brand", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.name or self.code


class ProductImage(UUIDModel, TimestampedModel):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="images",
    )
    image = models.ImageField(upload_to="catalog/products/")
    alt = models.CharField(max_length=200, blank=True, verbose_name="Alt-текст")
    sort_order = models.IntegerField(default=0)
    is_primary = models.BooleanField(default=False)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"

    def __str__(self) -> str:
        return f"{self.product_id} #{self.sort_order}"


class ProductSpec(UUIDModel):
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="spec",
    )
    protein_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Белок, %",
    )
    fat_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Жир, %",
    )
    fiber_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Клетчатка, %",
    )
    lysine_pct = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True, verbose_name="Лизин, %",
    )
    methionine_pct = models.DecimalField(
        max_digits=5, decimal_places=3, null=True, blank=True, verbose_name="Метионин, %",
    )
    me_kcal_per_kg = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ОЭ, ккал/кг",
    )
    moisture_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Влажность, %",
    )
    calcium_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Кальций, %",
    )
    phosphorus_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Фосфор, %",
    )
    extra = models.JSONField(
        default=dict, blank=True, verbose_name="Доп. показатели",
        help_text="JSON {key: value} для произвольных метрик",
    )

    class Meta:
        verbose_name = "Спецификация"
        verbose_name_plural = "Спецификации"


class CatalogPage(UUIDModel, TimestampedModel, SeoMixin):
    """Статичные страницы: about, contacts, erp, delivery, terms, privacy."""

    code = models.SlugField(unique=True, max_length=64, verbose_name="Технический код")
    slug = models.SlugField(max_length=160, verbose_name="URL-slug")
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    body = models.TextField(blank=True, verbose_name="Содержимое (markdown/HTML)")
    is_published = models.BooleanField(default=True, verbose_name="Опубликована")

    class Meta:
        ordering = ["code"]
        verbose_name = "Страница"
        verbose_name_plural = "Страницы"

    def __str__(self) -> str:
        return self.title or self.code


class ContactRequest(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=200, verbose_name="Имя")
    contact = models.CharField(max_length=200, verbose_name="Телефон / Email")
    company = models.CharField(max_length=200, blank=True, verbose_name="Компания")
    message = models.TextField(blank=True, verbose_name="Сообщение")
    source_lang = models.CharField(max_length=2, default="ru", verbose_name="Язык формы")
    source_url = models.URLField(blank=True, verbose_name="URL страницы")
    notified = models.BooleanField(default=False, verbose_name="Уведомление отправлено")
    user_agent = models.CharField(max_length=400, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка с каталога"
        verbose_name_plural = "Заявки с каталога"

    def __str__(self) -> str:
        return f"{self.name} / {self.contact}"
