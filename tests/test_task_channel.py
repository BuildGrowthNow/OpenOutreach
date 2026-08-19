from openoutreach.mongodb.models import Task


def test_task_defaults_to_linkedin_channel():
    t = Task(task_type=Task.TaskType.CONNECT, payload={"campaign_id": "c1"})
    assert t.channel == "linkedin"


def test_task_whatsapp_channel_serialises():
    t = Task(
        task_type=Task.TaskType.WHATSAPP_MESSAGE,
        payload={"campaign_id": "c1"},
        channel="whatsapp",
    )
    d = t.to_dict()
    assert d["channel"] == "whatsapp"


def test_task_roundtrip_channel():
    t = Task(
        task_type=Task.TaskType.WHATSAPP_FOLLOW_UP,
        payload={"campaign_id": "c1"},
        channel="whatsapp",
    )
    d = t.to_dict()
    t2 = Task.from_dict(d)
    assert t2.channel == "whatsapp"


def test_task_from_dict_missing_channel_defaults_linkedin():
    d = {"task_type": "connect", "payload": {"campaign_id": "c1"}}
    t = Task.from_dict(d)
    assert t.channel == "linkedin"
