import argparse

from ormik.fields import \
    ForeignKeyField, IntegerField, CharField, AutoField
from ormik.models import Model, CASCADE, NO_ACTION
from ormik.db import SqliteDatabase


def parse_user_settings():
    parser = argparse.ArgumentParser(
        description='Run test ORM project.'
    )
    parser.add_argument(
        '--db', default=':memory:', const=':memory:', type='str',
        help='Set db for ORM testing (default: %(default)'
    )
    return parser.parse_args()


def main():
    user_settings = parse_user_settings()

    class Author(Model):

        id = AutoField()
        name = CharField()

    class Book(Model):

        id = AutoField()
        author = ForeignKeyField(
            Author, 'books', is_nullable=True, on_delete=CASCADE
        )
        title = CharField(default='Title')
        pages = IntegerField(default=100)
        coauthor = ForeignKeyField(
            Author, 'cobooks', is_nullable=True, on_delete=NO_ACTION
        )
        rating = IntegerField(default=10)
        name = CharField(default='Book name')

    db = SqliteDatabase(user_settings.db)
    db.register_models([Author, Book])

    # Create table
    created = Author.create_table()
    created = Book.create_table()

    # Save
    author = Author(name='William Gibson')
    author.save()
    book = Book(author=author, title='Title', pages=100)
    book.save()
    book.pages = 123
    book.save()

    # CRUD
    book = Book.create(author=author, title='New', pages=80)
    updated_rows_num = Book.filter(pages=80).update(
        pages=10000, title='LOL!', author=author
    )
    deleted_rows_num = Book.filter(pages=10000).delete()

    # Select
    books = Book.values('title', 'pages', 'author__name')
    book = Book.get(id=1)
    books = Book.select_all()
    for book in Book.filter(pages__gt=10):
        pass
    for book in author.books:
        pass

    # Multiple filter
    books = Book.filter(
        author__name__contains='William Gibson'
    ).filter(pages__gt=10).values(
        'title', 'author__name'
    )

    # CASCADE delete
    Author.filter(id=1).delete()
    books = Book.select_all()

    # Drop table
    dropped = Author.drop_table()
    dropped = Book.drop_table()


if __name__ == '__main__':
    main()
