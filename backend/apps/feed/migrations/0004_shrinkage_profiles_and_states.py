import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0003_rawmaterialbatch_dockage_pct_actual_and_more"),
        ("nomenclature", "0006_seed_module_categories"),
        ("organizations", "0004_rename_default_org_name"),
        ("warehouses", "0006_stockmovement_shrinkage_kind"),
    ]

    operations = [
        migrations.CreateModel(
            name="FeedShrinkageProfile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "target_type",
                    models.CharField(
                        choices=[
                            ("ingredient", "Ингредиент (сырьё)"),
                            ("feed_type", "Тип готового корма"),
                        ],
                        db_index=True,
                        max_length=16,
                    ),
                ),
                (
                    "period_days",
                    models.PositiveSmallIntegerField(
                        help_text="Каждые сколько дней применяется процент усушки.",
                    ),
                ),
                (
                    "percent_per_period",
                    models.DecimalField(
                        decimal_places=3,
                        help_text="Сколько % от текущего остатка списывается за период (compound).",
                        max_digits=6,
                    ),
                ),
                (
                    "max_total_percent",
                    models.DecimalField(
                        blank=True,
                        decimal_places=3,
                        help_text="Верхний предел накопленной усушки на партию (% от initial). NULL = без предела.",
                        max_digits=6,
                        null=True,
                    ),
                ),
                (
                    "stop_after_days",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        help_text="Не списывать дольше N дней с поступления партии. NULL = без ограничения.",
                        null=True,
                    ),
                ),
                (
                    "starts_after_days",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Грейс-период: первые N дней после поступления усушка не считается.",
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("note", models.TextField(blank=True)),
                (
                    "nomenclature",
                    models.ForeignKey(
                        blank=True,
                        help_text="Заполняется при target_type=ingredient.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="feed_shrinkage_profiles",
                        to="nomenclature.nomenclatureitem",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="feed_shrinkage_profiles",
                        to="organizations.organization",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        blank=True,
                        help_text="Заполняется при target_type=feed_type. Один профиль действует на все версии рецепта и все партии готового корма по нему.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="feed_shrinkage_profiles",
                        to="feed.recipe",
                    ),
                ),
                (
                    "warehouse",
                    models.ForeignKey(
                        blank=True,
                        help_text="NULL = «для всех складов»; конкретный склад побеждает общий.",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="feed_shrinkage_profiles",
                        to="warehouses.warehouse",
                    ),
                ),
            ],
            options={
                "verbose_name": "Профиль усушки",
                "verbose_name_plural": "Профили усушки",
                "ordering": ["organization", "target_type", "-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="feedshrinkageprofile",
            index=models.Index(
                fields=["organization", "target_type", "is_active"],
                name="feed_feedsh_organiz_d4afa9_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="feedshrinkageprofile",
            index=models.Index(
                fields=["nomenclature", "warehouse"],
                name="feed_feedsh_nomencl_3a0d76_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="feedshrinkageprofile",
            index=models.Index(
                fields=["recipe", "warehouse"],
                name="feed_feedsh_recipe__c30b22_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedshrinkageprofile",
            constraint=models.CheckConstraint(
                check=models.Q(
                    models.Q(
                        ("nomenclature__isnull", False),
                        ("recipe__isnull", True),
                        ("target_type", "ingredient"),
                    ),
                    models.Q(
                        ("nomenclature__isnull", True),
                        ("recipe__isnull", False),
                        ("target_type", "feed_type"),
                    ),
                    _connector="OR",
                ),
                name="feed_shrinkage_profile_target_xor",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedshrinkageprofile",
            constraint=models.CheckConstraint(
                check=models.Q(("period_days__gt", 0)),
                name="feed_shrinkage_profile_period_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedshrinkageprofile",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("percent_per_period__gte", 0),
                    ("percent_per_period__lte", 100),
                ),
                name="feed_shrinkage_profile_pct_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedshrinkageprofile",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("max_total_percent__isnull", True),
                    models.Q(
                        ("max_total_percent__gte", 0),
                        ("max_total_percent__lte", 100),
                    ),
                    _connector="OR",
                ),
                name="feed_shrinkage_profile_max_pct_range",
            ),
        ),
        migrations.CreateModel(
            name="FeedLotShrinkageState",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "lot_type",
                    models.CharField(
                        choices=[
                            ("raw_arrival", "Партия сырья"),
                            ("production_batch", "Партия готового корма"),
                        ],
                        db_index=True,
                        max_length=24,
                    ),
                ),
                ("lot_id", models.UUIDField(db_index=True)),
                (
                    "initial_quantity",
                    models.DecimalField(decimal_places=3, max_digits=16),
                ),
                (
                    "accumulated_loss",
                    models.DecimalField(decimal_places=3, default=0, max_digits=16),
                ),
                (
                    "last_applied_on",
                    models.DateField(
                        blank=True,
                        help_text="Дата последнего цикла списания. NULL до первого применения.",
                        null=True,
                    ),
                ),
                (
                    "is_frozen",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="True когда достигнут max_total_percent / stop_after_days / остаток исчерпан.",
                    ),
                ),
                (
                    "organization",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="feed_lot_shrinkage_states",
                        to="organizations.organization",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="lot_states",
                        to="feed.feedshrinkageprofile",
                    ),
                ),
            ],
            options={
                "verbose_name": "Состояние усушки партии",
                "verbose_name_plural": "Состояния усушки партий",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.AddIndex(
            model_name="feedlotshrinkagestate",
            index=models.Index(
                fields=["organization", "lot_type", "is_frozen"],
                name="feed_feedlo_organiz_91d12c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="feedlotshrinkagestate",
            index=models.Index(
                fields=["profile", "is_frozen"],
                name="feed_feedlo_profile_3e2da4_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedlotshrinkagestate",
            constraint=models.UniqueConstraint(
                fields=("lot_type", "lot_id"),
                name="feed_lot_shrinkage_state_unique_lot",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedlotshrinkagestate",
            constraint=models.CheckConstraint(
                check=models.Q(
                    ("accumulated_loss__gte", 0),
                    ("accumulated_loss__lte", models.F("initial_quantity")),
                ),
                name="feed_lot_shrinkage_state_loss_within_initial",
            ),
        ),
    ]
