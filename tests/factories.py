# tests/factories.py
import factory  # type: ignore[import-untyped]
import factory.django  # type: ignore[import-untyped]
from django.contrib.auth import get_user_model
from faker import Faker

fake = Faker()
User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:  # type: ignore[misc]
        model = User

    username = factory.LazyFunction(fake.user_name)  # type: ignore[attr-defined]
    is_staff = True
    is_active = True


class LeadFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:  # type: ignore[misc]
        model = "crm.Lead"

    public_identifier = factory.Sequence(lambda n: f"lead-{n}")  # type: ignore[attr-defined]
    linkedin_url = factory.LazyAttribute(  # type: ignore[attr-defined]
        lambda o: f"https://www.linkedin.com/in/{o.public_identifier}/"
    )


class DealFactory(factory.django.DjangoModelFactory):  # type: ignore[misc]
    class Meta:  # type: ignore[misc]
        model = "crm.Deal"

    lead = factory.SubFactory(LeadFactory)  # type: ignore[attr-defined]
