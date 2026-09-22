from storage.engine import CollectionStore, NOW


_store = CollectionStore(
    name="youtube_subscriptions",

    defaults={
        "guild_id": None,
        "channel_id": None,
        "channel_name": None,
        "notification_channel_id": None,
        "role_id": None,
        "last_live_video_id": None,
        "created_at": NOW,
    },

    unique_sets=[
        ["guild_id", "channel_id"]
    ],

    json_fields=set(),

    datetime_fields={
        "created_at"
    },

    sequence_fields={},
)


async def create_table():
    return await _store.prepare()


async def insert(
    id=None,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
    created_at=None,
):
    return await _store.insert(locals())


async def update(
    id,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
    created_at=None,
):
    return await _store.update(locals())


async def get(
    id=None,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
    created_at=None,
):
    return await _store.get(locals())


async def gets(
    id=None,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
    created_at=None,
):
    return await _store.gets(locals())


async def delete(
    id=None,
    guild_id=None,
    channel_id=None,
    channel_name=None,
    notification_channel_id=None,
    role_id=None,
    last_live_video_id=None,
    created_at=None,
):
    return await _store.delete(locals())


async def get_all():
    return await _store.get_all()
