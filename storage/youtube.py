from storage.engine import CollectionStore


CollectionName = "youtube"

_store = CollectionStore(
    name=CollectionName,
    defaults={
        "guild_id": None,
        "channel_id": None,
        "channel_name": None,
        "uploads_playlist_id": None,
        "notification_channel_id": None,
        "role_id": None,
        "last_live_video_id": None,
    },
    unique_sets=[
        ["guild_id", "channel_id"],
    ],
    json_fields=set(),
    datetime_fields=set(),
    sequence_fields={},
    update_cache=[],
    delete_cache=[],
)


async def create_table():
    return await _store.prepare()


async def insert(
    id=None,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    uploads_playlist_id=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
):
    return await _store.insert(locals())


async def update(
    id,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    uploads_playlist_id=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
):
    return await _store.update(locals())


async def get(
    guild_id=None,
    channel_id=None,
    id=None,
):
    filters = {}

    if id is not None:
        filters["id"] = id

    if guild_id is not None:
        filters["guild_id"] = guild_id

    if channel_id is not None:
        filters["channel_id"] = channel_id

    return await _store.get(filters)


async def gets(
    guild_id=None,
    channel_id=None,
):
    filters = {}

    if guild_id is not None:
        filters["guild_id"] = guild_id

    if channel_id is not None:
        filters["channel_id"] = channel_id

    return await _store.gets(filters)


async def delete(
    id=None,
    guild_id=None,
    channel_id=None,
):
    filters = {}

    if id is not None:
        filters["id"] = id

    if guild_id is not None:
        filters["guild_id"] = guild_id

    if channel_id is not None:
        filters["channel_id"] = channel_id

    return await _store.delete(filters)


async def get_all():
    return await _store.get_all()
