"""OpenOutreach-specific LinkedIn runtime errors."""


class CloudProxyRequiredError(RuntimeError):
    """A cloud profile has no managed proxy and must not use the server IP."""

    def __init__(self, profile_id: str):
        self.profile_id = profile_id
        super().__init__("Cloud execution requires a managed proxy")
