from sqladmin import ModelView

from app.models.condominium import Condominium, OperatorAssignment
from app.models.product import Product, ProductPrice
from app.models.user import User


class UserAdmin(ModelView, model=User):
    name = "Usuário"
    name_plural = "Usuários"
    icon = "fa-solid fa-users"
    column_list = [User.id, User.username, User.full_name, User.role, User.is_active, User.created_at]
    column_searchable_list = [User.username, User.full_name]
    column_sortable_list = [User.id, User.username, User.role, User.is_active, User.created_at]
    column_details_exclude_list = [User.hashed_password, User.refresh_token_hash]
    form_excluded_columns = [User.hashed_password, User.refresh_token_hash, User.created_at]
    can_delete = False


class CondominiumAdmin(ModelView, model=Condominium):
    name = "Condomínio"
    name_plural = "Condomínios"
    icon = "fa-solid fa-building"
    column_list = [
        Condominium.id,
        Condominium.name,
        Condominium.erp_code,
        Condominium.commission_type,
        Condominium.commission_value,
        Condominium.onboarding_complete,
        Condominium.go_live_date,
    ]
    column_searchable_list = [Condominium.name, Condominium.erp_code]
    column_sortable_list = [Condominium.id, Condominium.name, Condominium.onboarding_complete]
    form_excluded_columns = [Condominium.created_at]


class OperatorAssignmentAdmin(ModelView, model=OperatorAssignment):
    name = "Atribuição de Operador"
    name_plural = "Atribuições de Operadores"
    icon = "fa-solid fa-user-tie"
    column_list = [OperatorAssignment.id, OperatorAssignment.user_id, OperatorAssignment.condominium_id]


class ProductAdmin(ModelView, model=Product):
    name = "Produto"
    name_plural = "Produtos"
    icon = "fa-solid fa-box"
    column_list = [
        Product.id,
        Product.name,
        Product.erp_product_code,
        Product.capacity_liters,
        Product.sort_order,
        Product.is_active,
    ]
    column_sortable_list = [Product.sort_order, Product.name]
    form_excluded_columns = [Product.created_at]


class ProductPriceAdmin(ModelView, model=ProductPrice):
    name = "Preço de Produto"
    name_plural = "Preços de Produtos"
    icon = "fa-solid fa-tag"
    column_list = [
        ProductPrice.id,
        ProductPrice.product_id,
        ProductPrice.condominium_id,
        ProductPrice.unit_price,
        ProductPrice.source,
        ProductPrice.valid_from,
    ]
    column_sortable_list = [ProductPrice.valid_from, ProductPrice.unit_price]
