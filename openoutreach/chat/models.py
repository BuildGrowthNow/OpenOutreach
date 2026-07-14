# Chat models are now MongoDB-native
# This module re-exports from mongodb.models_extended for backward compatibility
from openoutreach.mongodb.models_extended import ChatMessage

__all__ = ["ChatMessage"]
