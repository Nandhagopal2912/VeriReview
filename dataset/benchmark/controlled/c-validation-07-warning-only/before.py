import logging

logger = logging.getLogger(__name__)


def rename(person, name):
    person.name = name
    person.save()
