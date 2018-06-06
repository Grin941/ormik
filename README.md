# ormik
[![Build Status](https://travis-ci.org/Grin941/ormik.svg?branch=master)](https://travis-ci.org/Grin941/ormik)
[![Coverage by codecov.io](https://codecov.io/gh/Grin941/ormik/branch/master/graphs/badge.svg?branch=master)](https://codecov.io/gh/Grin941/ormik?branch=master)
[![Maintainability](https://api.codeclimate.com/v1/badges/1f9af56bd402081cefa2/maintainability)](https://codeclimate.com/github/Grin941/ormik/maintainability)

My ORM Implementation.

## Requirements

* Python 3.6
* Support sqlite

## Installation

```
$ make
```

## Usage

To run built-in test ORM project type:

```
$ orm [db]
```

## QuickStart

Defining models is similar to Django or SQLAlchemy
(You may also define table name):

```
from ormik import models, fields


class Author(models.Model):

    id = fields.AutoField()
    name = fields.CharField()

class Book(models.Model):
    __tablename__ = 'good_books'

    id = fields.AutoField()
    author = fields.ForeignKeyField(
        Author, 'books', is_nullable=True, on_delete=CASCADE
    )
    title = fields.CharField(default='Title')
    pages = fields.IntegerField(default=100)
```

Connect to database and register tables:

```
from ormik import db

database = db.SqliteDatabase('tmp.db')
database.register_models([Author, Book])
```

Create table:

```
created = Author.create_table()
created = Book.create_table()
```

Save models:

```
author = Author(name='William Gibson')
author.save()
book = Book(author=author, title='Neuromancer', pages=100)
book.save()
book.pages = 271
book.save()
```

CRUD:

```
book = Book.create(author=author, title='Count Zero', pages=80)
updated_rows_num = Book.filter(pages=80).update(pages=256)
deleted_rows_num = Book.filter(pages=256).delete()
```

SELECT:

```
books = Book.values('title', 'pages', 'author__name')
book = Book.get(id=1)
books = Book.select_all()
for book in Book.filter(pages__gt=10):
    # Select results are iterable
    pass
for book in author.books:
    # ReversedForeignKey is iterable too
    pass
```

Filters may be multiplied:

```
books = Book.filter(
    author__name__contains='William Gibson'
).filter(pages__gt=10).values(
    'title', 'author__name'
)
```

CASCADE delete:

```
Author.filter(id=1).delete()
books = Book.select_all()  # Books would be deleted CASCADE
```

Drop table:

```
dropped = Author.drop_table()
dropped = Book.drop_table()
```

## Fields

Note: only one PK may be defined. Elsewhere ```PkCountError``` exception would be raised.

```
CharField(is_nullable=True, default=None, primary_key=False, max_length=128)
IntegerField(is_nullable=True, default=None, primary_key=False)
BooleanField(is_nullable=True, default=None, primary_key=False)
ForeignKeyField(model, reversed_name, is_nullable=True, default=None, primary_key=False, on_delete=NO_ACTION, on_update=NO_ACTION)
AutoField(is_nullable=True, default=None, primary_key=True)
```

## Lookup operations

Lookup operations used in filter(),
for instance, ```Model.filter(field__gt=10)```:

```
__exact    ->    =
__gt       ->    >
__gte      ->    >=
__lt       ->    <
__lte      ->    <=
__contains ->    LIKE
__in       ->    IN
```

## Lookups that span relationships

To span a relationship, just use the field name of related fields across models, separated by double underscores, until you get to the field you want.
SQL ```Join``` would be made for you.
Note that only one relationship lookup are available:

```
blog__name            ->    OK
magazine__blog__name  ->    NOT OK
```

## Queryset methods

```
filter(**kwargs)
```

Returns a new QuerySet containing objects that match the given lookup parameters.

```
values(*fields)
```

Returns list of dictionaries, rather than model instances, when used as an iterable.
You may get FK fields: ```values('fk__field')```.

```
select_all()
```

Returns list of model instances.

```
get(**kwargs)
```

Returns the object matching the given lookup parameters.
If object not exist ```ObjectDoesNotExist``` exception would be raised.
If multiple objects returned ```MultipleObjectsReturned``` exception would be raised. 

```
create(**kwargs)
```

A convenience method for creating an object and saving it all in one step.
Method returns instance created.

```
update(**kwargs)
```

Performs an SQL update query for the specified fields, and returns the number of rows matched .
Note: FK fields may not be updated (fk__field is not supported in kwargs).

```
delete()
```

Performs an SQL delete query on all rows in the QuerySet and returns the number of objects deleted.

```
create_table()
```

Creates Model as a DB table.

```
drop_table()
```

## Testing

```
$ PYTHONPATH=. pytest
```
