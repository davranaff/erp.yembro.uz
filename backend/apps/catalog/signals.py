"""
post_save/post_delete сигналы → triggering ISR revalidation на Next.js.
"""
from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Brand, CatalogPage, Category, Product, ProductImage
from .tasks import revalidate_next_task


def _enqueue(tags: list[str]) -> None:
    # `sitemap` всегда обновляется при любой структурной правке.
    tags = list({*tags, "sitemap"})
    revalidate_next_task.delay(tags)


@receiver([post_save, post_delete], sender=Product)
def _product_changed(sender, instance: Product, **kwargs):
    code = getattr(instance, "code", "")
    cat_code = getattr(getattr(instance, "category", None), "code", "")
    brand_code = getattr(getattr(instance, "brand", None), "code", "")
    _enqueue([
        f"product:{code}",
        f"category:{cat_code}",
        f"brand:{brand_code}",
        "products",
    ])


@receiver([post_save, post_delete], sender=ProductImage)
def _product_image_changed(sender, instance: ProductImage, **kwargs):
    # При загрузке/удалении фото у товара мы должны инвалидировать
    # не только страницу товара, но и общий список (`products`) —
    # карточка в списке зависит от primary_image.
    product = getattr(instance, "product", None)
    code = getattr(product, "code", "") if product else ""
    cat_code = getattr(getattr(product, "category", None), "code", "") if product else ""
    brand_code = getattr(getattr(product, "brand", None), "code", "") if product else ""
    _enqueue([
        f"product:{code}",
        f"category:{cat_code}",
        f"brand:{brand_code}",
        "products",
    ])


@receiver([post_save, post_delete], sender=Category)
def _category_changed(sender, instance: Category, **kwargs):
    _enqueue([f"category:{instance.code}", "categories"])


@receiver([post_save, post_delete], sender=Brand)
def _brand_changed(sender, instance: Brand, **kwargs):
    _enqueue([f"brand:{instance.code}", "brands"])


@receiver([post_save, post_delete], sender=CatalogPage)
def _page_changed(sender, instance: CatalogPage, **kwargs):
    _enqueue([f"page:{instance.code}"])
