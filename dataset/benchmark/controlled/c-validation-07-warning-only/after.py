import logging

logger = logging.getLogger(__name__)


def rename(person, name):
    if not name:
        logger.warning("empty name for person %s", person.id)
    person.name = name
    person.save()
