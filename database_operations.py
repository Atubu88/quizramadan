import logging
from sqlalchemy.exc import DataError, IntegrityError
from database import session  # Предположим, что session создается в модуле database
from models import User  # Модель User, которая соответствует таблице users в базе данных


def add_user(telegram_id, username, first_name, last_name):
    try:
        # Добавляем нового пользователя в базу данных
        new_user = User(telegram_id=telegram_id, username=username, first_name=first_name, last_name=last_name)
        session.add(new_user)
        session.commit()  # Фиксируем транзакцию
        logging.info(f"Пользователь {first_name} успешно добавлен")
    except DataError as e:
        session.rollback()  # Откатываем транзакцию, если данные некорректны
        logging.error(f"Ошибка базы данных: {e}")
    except IntegrityError as e:
        session.rollback()  # Откатываем транзакцию, если нарушены ограничения целостности
        logging.error(f"Ошибка целостности данных: {e}")
    except Exception as e:
        session.rollback()  # Откатываем транзакцию в случае других ошибок
        logging.error(f"Произошла ошибка: {e}")
    finally:
        session.close()  # Закрываем сессию


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Вызываем функцию добавления пользователя
    add_user(telegram_id=5791896027, username=None, first_name='Abdullah', last_name=None)
