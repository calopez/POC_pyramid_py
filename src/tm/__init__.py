# -*- coding: utf-8 -*-
import os
import typing as t

from pkg_resources import get_distribution, DistributionNotFound

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = __name__
    __version__ = get_distribution(dist_name).version
except DistributionNotFound:
    __version__ = 'unknown'
finally:
    del get_distribution, DistributionNotFound


from pyramid.config import Configurator
from tm.system.core.utils import expandvars_dict

def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """

    config = Configurator(settings=expandvars_dict(settings))
    config.include('.conf.secrets')
    config.include('.conf.templates')

    config.include('.models')
    config.include('.routes')
    config.scan()
    return config.make_wsgi_app()

