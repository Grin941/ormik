import argparse

from ormik import fields, models, db, sql


def parse_user_settings():
    parser = argparse.ArgumentParser(
        description='Run test ORM project.'
    )
    parser.add_argument(
        '--db', default=':memory:', type=str,
        help='Set db for ORM testing (default: %(default))'
    )
    return parser.parse_args()


def main():
    user_settings = parse_user_settings()

    class Author(models.Model):

        id = fields.AutoField()
        name = fields.CharField()

    class Book(models.Model):
        __tablename__ = 'good_books'

        id = fields.AutoField()
        author = fields.ForeignKeyField(
            Author, 'books', is_nullable=True, on_delete=sql.CASCADE
        )
        title = fields.CharField(default='Title')
        pages = fields.IntegerField(default=100)
        coauthor = fields.ForeignKeyField(
            Author, 'cobooks', is_nullable=True, on_delete=sql.NO_ACTION
        )
        rating = fields.IntegerField(default=10)
        name = fields.CharField(default='Book name')

    database = db.SqliteDatabase(user_settings.db)
    database.register_models([Author, Book])

    # Create table
    created = Author.create_table()
    print('Author table created', created)
    created = Book.create_table()
    print('Book table created', created)

    # Save
    author = Author(name='William Gibson')
    author.save()
    print('Author created', author)
    book = Book(author=author, title='Title', pages=100)
    book.save()
    book.pages = 123
    book.save()
    print('Book created', book)

    # CRUD
    book = Book.create(author=author, title='New', pages=80)
    print('Book created', book)
    updated_rows_num = Book.filter(pages=80).update(
        pages=10000, title='LOL!', author=author
    )
    print(updated_rows_num, 'Books updated')
    deleted_rows_num = Book.filter(pages__in=[10000, 1234]).delete()
    print(deleted_rows_num, 'Books deleted')

    # Select
    books = Book.values('title', 'pages', 'author__name')
    print('Books values', books)
    book = Book.get(id=1)
    print('Book selected', book)
    books = Book.select_all()
    print('All books', books)

    print('Filter books')
    for book in Book.filter(pages__gt=10, author=author):
        print(book)
    print('Author books')
    for book in author.books:
        print(book)

    # Multiple filter
    books = Book.filter(
        author__name__contains='William Gibson'
    ).filter(pages__gt=10).values(
        'title', 'author__name'
    )
    print('Multiple filters', books)

    # CASCADE delete
    Author.filter(id=1).delete()
    books = Book.select_all()
    print('Books CASCADE removed', books)

    # Drop table
    dropped = Author.drop_table()
    print('Author dropped', dropped)
    dropped = Book.drop_table()
    print('Book dropped', dropped)


if __name__ == '__main__':
    main()
