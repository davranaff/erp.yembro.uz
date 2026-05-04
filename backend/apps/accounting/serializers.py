from rest_framework import serializers

from .models import ExpenseArticle, GLAccount, GLSubaccount, JournalEntry


class GLSubaccountSerializer(serializers.ModelSerializer):
    account_code = serializers.SerializerMethodField()
    account_name = serializers.SerializerMethodField()
    module_code = serializers.SerializerMethodField()

    class Meta:
        model = GLSubaccount
        fields = (
            "id",
            "account",
            "module",
            "code",
            "name",
            "account_code",
            "account_name",
            "module_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "account_code",
            "account_name",
            "module_code",
            "created_at",
            "updated_at",
        )

    def get_account_code(self, obj):
        return obj.account.code if obj.account_id else None

    def get_account_name(self, obj):
        return obj.account.name if obj.account_id else None

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def validate(self, attrs):
        # Проверка: account должен принадлежать организации из контекста.
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None
        account = attrs.get("account") or (self.instance.account if self.instance else None)
        if org and account and account.organization_id != org.id:
            raise serializers.ValidationError(
                {"account": "Счёт из другой организации."}
            )
        # Проверка уникальности (account, code) без учёта orgs — unique_together есть на модели,
        # но DRF даст 500 если не поймать здесь.
        code = attrs.get("code") or (self.instance.code if self.instance else None)
        if account and code:
            qs = GLSubaccount.objects.filter(account=account, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": f"Субсчёт с кодом {code} уже существует у счёта {account.code}."}
                )
        return attrs


class GLAccountSerializer(serializers.ModelSerializer):
    subaccounts = GLSubaccountSerializer(many=True, read_only=True)

    class Meta:
        model = GLAccount
        fields = (
            "id",
            "code",
            "name",
            "type",
            "subaccounts",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "subaccounts",
            "created_at",
            "updated_at",
        )


class ExpenseArticleSerializer(serializers.ModelSerializer):
    default_subaccount_code = serializers.CharField(
        source="default_subaccount.code", read_only=True, default=None, allow_null=True,
    )
    default_subaccount_name = serializers.CharField(
        source="default_subaccount.name", read_only=True, default=None, allow_null=True,
    )
    default_module_code = serializers.CharField(
        source="default_module.code", read_only=True, default=None, allow_null=True,
    )
    parent_code = serializers.CharField(
        source="parent.code", read_only=True, default=None, allow_null=True,
    )
    parent_name = serializers.CharField(
        source="parent.name", read_only=True, default=None, allow_null=True,
    )

    class Meta:
        model = ExpenseArticle
        fields = (
            "id",
            "code",
            "name",
            "kind",
            "default_subaccount",
            "default_subaccount_code",
            "default_subaccount_name",
            "default_module",
            "default_module_code",
            "parent",
            "parent_code",
            "parent_name",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "default_subaccount_code",
            "default_subaccount_name",
            "default_module_code",
            "parent_code",
            "parent_name",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        request = self.context.get("request")
        org = getattr(request, "organization", None) if request else None

        sub = attrs.get("default_subaccount") or (
            self.instance.default_subaccount if self.instance else None
        )
        if org and sub and sub.account.organization_id != org.id:
            raise serializers.ValidationError(
                {"default_subaccount": "Субсчёт из другой организации."}
            )

        parent = attrs.get("parent") or (self.instance.parent if self.instance else None)
        if org and parent and parent.organization_id != org.id:
            raise serializers.ValidationError(
                {"parent": "Родительская статья из другой организации."}
            )
        if self.instance and parent and parent.id == self.instance.id:
            raise serializers.ValidationError(
                {"parent": "Статья не может быть родителем сама себе."}
            )

        # Уникальность (org, code)
        code = attrs.get("code") or (self.instance.code if self.instance else None)
        if org and code:
            qs = ExpenseArticle.objects.filter(organization=org, code=code)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"code": f"Статья с кодом {code} уже существует."}
                )
        return attrs


class JournalEntrySerializer(serializers.ModelSerializer):
    debit_code = serializers.SerializerMethodField()
    credit_code = serializers.SerializerMethodField()
    module_code = serializers.SerializerMethodField()
    currency_code = serializers.SerializerMethodField()
    counterparty_name = serializers.SerializerMethodField()
    batch_doc_number = serializers.SerializerMethodField()
    expense_article_code = serializers.CharField(
        source="expense_article.code", read_only=True, default=None, allow_null=True,
    )
    expense_article_name = serializers.CharField(
        source="expense_article.name", read_only=True, default=None, allow_null=True,
    )

    class Meta:
        model = JournalEntry
        fields = (
            "id",
            "doc_number",
            "module",
            "entry_date",
            "description",
            "debit_subaccount",
            "credit_subaccount",
            "amount_uzs",
            "currency",
            "amount_foreign",
            "exchange_rate",
            "source_content_type",
            "source_object_id",
            "counterparty",
            "batch",
            "expense_article",
            "expense_article_code",
            "expense_article_name",
            "debit_code",
            "credit_code",
            "module_code",
            "currency_code",
            "counterparty_name",
            "batch_doc_number",
            "created_at",
        )
        read_only_fields = fields  # создаётся только сервисами

    def get_debit_code(self, obj):
        return obj.debit_subaccount.code if obj.debit_subaccount_id else None

    def get_credit_code(self, obj):
        return obj.credit_subaccount.code if obj.credit_subaccount_id else None

    def get_module_code(self, obj):
        return obj.module.code if obj.module_id else None

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None

    def get_counterparty_name(self, obj):
        return obj.counterparty.name if obj.counterparty_id else None

    def get_batch_doc_number(self, obj):
        return obj.batch.doc_number if obj.batch_id else None


# ─── Cash advance ─────────────────────────────────────────────────────────


class CashAdvanceSerializer(serializers.ModelSerializer):
    recipient_name = serializers.SerializerMethodField()
    expense_article_code = serializers.SerializerMethodField()
    expense_article_name = serializers.SerializerMethodField()
    closing_je_doc = serializers.SerializerMethodField()

    class Meta:
        from .models import CashAdvance

        model = CashAdvance
        fields = (
            "id",
            "doc_number",
            "issued_date",
            "closed_date",
            "recipient",
            "recipient_name",
            "purpose",
            "amount_uzs",
            "spent_amount_uzs",
            "returned_amount_uzs",
            "expense_article",
            "expense_article_code",
            "expense_article_name",
            "status",
            "issued_payment",
            "closing_journal_entry",
            "closing_je_doc",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "doc_number",
            "spent_amount_uzs",      # меняется через action /report/
            "returned_amount_uzs",
            "closed_date",
            "status",                # меняется через actions
            "issued_payment",
            "closing_journal_entry",
            "recipient_name",
            "expense_article_code",
            "expense_article_name",
            "closing_je_doc",
            "created_at",
            "updated_at",
        )

    def get_recipient_name(self, obj):
        u = obj.recipient
        if not u:
            return None
        return u.full_name or u.email

    def get_expense_article_code(self, obj):
        return obj.expense_article.code if obj.expense_article_id else None

    def get_expense_article_name(self, obj):
        return obj.expense_article.name if obj.expense_article_id else None

    def get_closing_je_doc(self, obj):
        return obj.closing_journal_entry.doc_number if obj.closing_journal_entry_id else None
