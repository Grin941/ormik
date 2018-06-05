from ormik import QueryError, fields

__all__ = ['FieldSQL', 'QueryError']


NULL = 'NULL'

CASCADE = 'CASCADE'
RESTRICT = 'RESTRICT'
SET_NULL = 'SET_NULL'
NO_ACTION = 'NO ACTION'


class FieldSQL:

    SQL_TYPES_MAPPING = {
        str: 'VARCHAR',
        int: 'INTEGER',
        bool: 'BOOLEAN',
    }

    def __init__(self, field, *args, **kwargs):
        self.field = field

    def _generate_field_sql(self):
        field = self.field
        field_type = int if not hasattr(field, 'ty') else field.ty
        field_is_autoincremented = isinstance(field, fields.AutoField)
        sql = f'{field.name} {self.SQL_TYPES_MAPPING[field_type]}'

        if hasattr(field, 'max_length'):
            sql += f'({field.max_length})'

        if field.is_primary_key:
            sql += f' PRIMARY KEY'

        if not (field.is_nullable or field_is_autoincremented):
            sql += f' NOT {NULL}'

        if field.default_value is not None:
            sql += f' DEFAULT "{field.default_value}"'

        if field_is_autoincremented:
            sql += f' AUTOINCREMENT'

        return sql

    def _generate_fk_constraints(self):
        field = self.field
        return (
            f' FOREIGN KEY ({field.name})'
            f' REFERENCES {field.rel_model._table}'
            f' ({field.rel_model._pk.name})'
            f' ON DELETE {field.on_delete} ON UPDATE {field.on_update}'
        ) if isinstance(field, fields.ForeignKeyField) else None

    @property
    def column_definition(self):
        return self._generate_field_sql()

    @property
    def table_constraints(self):
        return self._generate_fk_constraints()


def _normalize_lookup_value(lookup_statement, lookup_value):
    if lookup_statement == 'LIKE':
        lookup_value = f"'%{lookup_value}%'"
    elif lookup_statement == 'IN':
        lookup_value = f'{tuple(lookup_value)}'
    else:
        if isinstance(lookup_value, str):
            lookup_value = f"'{lookup_value}'"

    return lookup_value


def _normalize_field_value(field_value):
    if isinstance(field_value, str):
        field_value = f"'{field_value}'"
    if field_value is None:
        field_value = NULL
    return field_value


class QuerySQL:

    PRIMARY_MODEL_KEY = 'PRIMARYMODELKEY'

    FIELD_LOOKUP_MAPPING = {
        'exact': '=',
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<=',
        'contains': 'LIKE',
        'in': 'IN',
        'is': 'IS',
    }

    def __init__(self, model, *args, **kwargs):
        self.model = model
        self.query_statements = {}
        self.fk_joins = {
            self.PRIMARY_MODEL_KEY: 't0'
        }

    @property
    def should_be_joined(self):
        return len(self.fk_joins) > 1

    @property
    def create_table_stmt(self):
        columns_definition_list, table_constraints_list = [], []
        for field in self.model._fields.values():
            columns_definition_list.append(
                field.query.column_definition
            )
            table_constraints = field.query.table_constraints
            if table_constraints is not None:
                table_constraints_list.append(table_constraints)
        columns_definition_sql = ', '.join(columns_definition_list)
        table_constraints_sql = ', '.join(table_constraints_list)
        if table_constraints_sql:
            columns_definition_sql = f'{columns_definition_sql},'

        return (
            f'CREATE TABLE IF NOT EXISTS {self.model._table} ('
            f'{columns_definition_sql}'
            f'{table_constraints_sql}'
            f')'
        )

    @property
    def drop_table_stmt(self):
        return f'DROP TABLE {self.model._table}'

    @property
    def insert_stmt(self):
        (
            sql_columns_statement,
            sql_values_statement
        ) = self._sql_insert_statement()

        return (
            f'INSERT INTO {self.model._table}({sql_columns_statement}) '
            f'VALUES ({sql_values_statement})'
        )

    @property
    def select_stmt(self):
        sql_select_statement = self._sql_select_statement()
        sql_from_statement = self._sql_from_statement()
        sql_where_statement = self._sql_where_statement()

        sql = (
            f'SELECT {sql_select_statement} '
            f'FROM {sql_from_statement}'
        )

        if sql_where_statement:
            sql += f' WHERE {sql_where_statement}'

        return sql

    @property
    def delete_stmt(self):
        if self.should_be_joined:
            sql_where_statement = (
                f'{self.model._pk.name} IN ({self.select_stmt})'
            )
        else:
            sql_where_statement = self._sql_where_statement(
                split_table_alias=True
            )

        return (
            f'DELETE FROM {self.model._table} '
            f'WHERE {sql_where_statement}'
        )

    @property
    def update_stmt(self):
        if self.should_be_joined:
            raise QueryError(
                'QuerySet can only update columns in the model’s main table'
            )
        sql_update_statement = self._sql_update_statement()
        sql_where_statement = self._sql_where_statement(split_table_alias=True)

        sql = (
            f'UPDATE {self.model._table} '
            f'SET {sql_update_statement}'
        )

        if sql_where_statement:
            sql += f' WHERE {sql_where_statement}'

        return sql

    def _sql_insert_statement(self):
        columns, values = [], []
        for field, (
            _, field_value
        ) in self.query_statements['INSERT']['lookups'].items():
            table_alias, field_name = field.split('.')
            field_value = _normalize_field_value(field_value)

            columns.append(f"'{field_name}'")
            values.append(f"{field_value}")

        return ', '.join(columns), ', '.join(values)

    def _sql_update_statement(self):
        sql_update_statement = []
        for field, (
            _, value
        ) in self.query_statements['UPDATE']['lookups'].items():
            table_alias, field_name = field.split('.')
            if field_name == self.model._pk.name:
                # PK can not be updated
                continue
            value = _normalize_field_value(value)
            sql_update_statement.append(f'{field_name} = {value}')
        return ', '.join(sql_update_statement)

    def _sql_select_statement(self):
        select_fields = self.query_statements['SELECT']['fields']
        sql_select_statement = ', '.join(
            select_fields
        ) if select_fields else ', '.join(
            [f'{alias}.*' for alias in self.fk_joins.values()]
        )
        return sql_select_statement

    def _sql_from_statement(self):
        sql_from_statement = (
            f'{self.model._table} '
            f'AS {self.fk_joins.pop(self.PRIMARY_MODEL_KEY)}'
        )
        for field, table_alias in self.fk_joins.items():
            sql_from_statement += (
                f' LEFT JOIN {self.model._fields[field].rel_model._table} '
                f'AS {table_alias} '
                f'ON t0.{field} = '
                f'{table_alias}.{self.model._fields[field].rel_model._pk.name}'
            )
        return sql_from_statement

    def _sql_where_statement(self, split_table_alias=False):
        if 'WHERE' not in self.query_statements:
            return

        sql_where_statement = []
        for field_name, (
            lookup_statement, lookup_value
        ) in self.query_statements['WHERE']['lookups'].items():
            if split_table_alias:
                table_alias, field_name = field_name.split('.')
            lookup_value = _normalize_lookup_value(
                lookup_statement, lookup_value
            )
            sql_where_statement.append(
                f'{field_name} {lookup_statement} {lookup_value}'
            )
        return ' AND '.join(sql_where_statement)

    def _fill_statement_fields(
        self,
        statement_fields, with_fields_alias=False,
        *args
    ):
        fk_joins = self.fk_joins
        for field_name in args:
            field_alias = field_name
            fk = self.PRIMARY_MODEL_KEY
            if '__' in field_name:
                # Field name is FK
                fk, field_name = field_name.split('__')
                if fk not in fk_joins:
                    fk_joins[fk] = f't{len(fk_joins)}'
            statement_field = f'{fk_joins[fk]}.{field_name}'
            if with_fields_alias:
                statement_field += f' AS {field_alias}'

            statement_fields.append(statement_field)

    def _fill_statement_lookups(self, statement_lookups, **kwargs):
        fk_joins = self.fk_joins
        for field_lookup, lookup_value in kwargs.items():
            fk = self.PRIMARY_MODEL_KEY
            field_lookup_bricks = field_lookup.split('__')
            if field_lookup_bricks[-1] not in self.FIELD_LOOKUP_MAPPING:
                field_lookup_bricks.append('exact')

            if len(field_lookup_bricks) > 2:
                # Field is FK
                fk = field_lookup_bricks.pop(0)

            field_name, lookup_statement = field_lookup_bricks
            if fk not in fk_joins:
                fk_joins[fk] = f't{len(fk_joins)}'

            statement_lookups[
                f'{fk_joins[fk]}.{field_name}'
            ] = (
                f'{self.FIELD_LOOKUP_MAPPING[lookup_statement]}', lookup_value
            )

    def append_statement(
            self,
            statement_alias,
            *args, with_fields_alias=False, **kwargs
    ):
        query_statement_dict = self.query_statements
        statement_meta = {
            'fields': [],
            'lookups': {}
        } if statement_alias not in query_statement_dict else \
            query_statement_dict[statement_alias]

        self._fill_statement_fields(
            statement_meta['fields'], with_fields_alias, *args
        )
        self._fill_statement_lookups(statement_meta['lookups'], **kwargs)

        query_statement_dict[statement_alias] = statement_meta
