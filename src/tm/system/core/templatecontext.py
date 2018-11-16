"""Application template filters ."""
# Standard Library
import datetime
import json
import typing as t

# Pyramid
from jinja2 import Markup
from jinja2 import contextfilter
from pyramid.config import Configurator
from pyramid.renderers import render
from pyramid.threadlocal import get_current_request

# System
from tm.utils import slug, time
from tm.utils import html


@contextfilter
def uuid_to_slug(jinja_ctx, context, **kw):
    """Convert UUID object to a base64 encoded slug.

    Example:

    .. code-block:: html+jinja

        {% for question in latest_question_list %}
            <li>
              <a href="{{ route_url('details', question.uuid|uuid_to_slug) }}">
                {{ question.question_text }}
              </a>
            </li>
        {% endfor %}

    """
    return slug.uuid_to_slug(context)


@contextfilter
def filter_datetime(jinja_ctx, context, **kw):
    """Format datetime in a certain timezone."""
    return time.format_dt_tz(context, kw)


@contextfilter
def arrow_format(jinja_ctx, context, *args, **kw):
    """Format datetime using Arrow formatter string.

    Context must be a time/datetime object.

    :term:`Arrow` is a Python helper library for parsing and formatting datetimes.

    Example:

    .. code-block:: html+jinja

        <li>
          Offer created at {{ offer.created_at|arrow_format('YYYYMMDDHHMMss') }}
        </li>

    `See Arrow formatting <http://crsmithdev.com/arrow/>`__.
    """
    assert len(args) == 1, "We take exactly one formatter argument, got {}".format(args)
    assert isinstance(context, (datetime.datetime, datetime.time)), "Got context {}".format(context)
    return time.arrow_format(dt=context, dt_format=args[0])


@contextfilter
def friendly_time(jinja_ctx, context, **kw):
    """Format timestamp in human readable format.

    * Context must be a datetime object

    * Takes optional keyword argument timezone which is a timezone name as a string. Assume the source datetime is in
    this timezone.
    """

    tz = kw.get("source_timezone", None)
    return time.friendly_time(now=context, tz=tz)

@contextfilter
def escape_js(jinja_ctx, context, **kw):
    """Make JSON strings to safe to be embedded inside <script> tag."""
    markup = Markup(html.escape_js(context))
    return markup


@contextfilter
def to_json(jinja_ctx, context, safe=True):
    """Converts Python dict to JSON, safe to be placed inside <script> tag.

    Example:

    .. code-block:: html+jinja

            {#
              Export server side generated graph data points
              to Rickshaw client side graph rendering
            #}
            {% if graph_data %}
              <script>
                window.graphDataJSON = "{{ graph_data|to_json }}";
              </script>
            {% endif %}

    :param context: Takes Python dictionary as input

    :param safe: Set to False to not to run ``escape_js()`` on the resulting JSON. True by default.

    :return: JSON string to be included inside HTML code
    """
    json_ = json.dumps(context)
    if safe:
        return escape_js(jinja_ctx, json_)
    else:
        return json_


@contextfilter
def timestruct(jinja_ctx, context, **kw):
    """Render both humanized time and accurate time.

    * show_timezone

    * target_timezone

    * source_timezone

    * format
    """
    if not context:
        return ""

    assert type(context) in (datetime.datetime, datetime.time,)

    request = jinja_ctx.get('request') or get_current_request()
    if not jinja_ctx:
        return ""

    kw = kw.copy()
    kw["time"] = context
    kw["format"] = kw.get("format") or "YYYY-MM-DD HH:mm"

    return Markup(render("core/timestruct.html", kw, request=request))


@contextfilter
def from_timestamp(jinja_ctx, context, **kw):
    """Convert UNIX datetime to timestamp.

    Example:

    .. code-block:: html+jinja

        <p>
            Prestodoctor license expires: {{ prestodoctor.recommendation.expires|from_timestamp(timezone="US/Pacific")|friendly_time }}
        </p>

    :param context: UNIX timestamps as float as seconds since 1970
    :return: Python datetime object
    """

    tz = kw.get("timezone")
    assert tz, "You need to give an explicit timezone when converting UNIX times to datetime objects"
    return time.from_timestamp(unix_dt=context, tz=tz)


def include_filter(config: Configurator, name: str, func: t.Callable, renderers=(".html", ".txt",)):
    """Register a new Jinja 2 template filter function.

    Example::

        import jinja2

        @jinja2.contextfilter
        def negative(jinja_ctx:jinja2.runtime.Context, context:object, **kw):
            '''Output the negative number.

            Usage:

                {{ 3|neg }}

            '''
            neg = -context
            return neg


    Then in your initialization:::

        include_filter(config, "neg", negative)

    :param config: Pyramid configurator

    :param name: Filter name in templates

    :param func: Python function which is the filter

    :param renderers: List of renderers where the filter is made available

    """

    def _include_filter(name, func):

        def deferred():
            for renderer_name in renderers:
                env = config.get_jinja2_environment(name=renderer_name)
                assert env, "Jinja 2 not configured - cannot add filters"
                env.filters[name] = func

        # Because Jinja 2 engine is not initialized here, only included here, we need to do template filter including
        # asynchronously
        config.action('pyramid_web-include-filter-{}'.format(name), deferred, order=1)

    _include_filter(name, func)


def includeme(config):
    include_filter(config, "uuid_to_slug", uuid_to_slug)
    include_filter(config, "friendly_time", friendly_time)
    include_filter(config, "datetime", filter_datetime)
    include_filter(config, "escape_js", escape_js)
    include_filter(config, "timestruct", timestruct)
    include_filter(config, "to_json", to_json)
    include_filter(config, "from_timestamp", from_timestamp)
    include_filter(config, "arrow_format", arrow_format)
