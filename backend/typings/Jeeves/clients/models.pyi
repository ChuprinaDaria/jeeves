from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from typing import ForwardRef
from django.db.models import Model, Manager
from django.db.models.fields import AutoField, CharField, TextField, BooleanField, BigIntegerField, DateTimeField, PositiveIntegerField
from django.db.models.fields.related import OneToOneField, ForeignKey
from django.db.models.fields.files import ImageField, FileField
from django.db.models.fields.json import JSONField
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

class Client(Model):
    objects: Manager[Client]
    id: AutoField
    user: OneToOneField[Any, Any]
    specialization: ForeignKey[Any, Any]
    company_name: CharField
    logo: ImageField
    is_active: BooleanField
    client_type: CharField
    features: JSONField
    custom_system_prompt: TextField
    created_by: ForeignKey[Any, Any]
    created_at: DateTimeField
    updated_at: DateTimeField
    
    def has_feature(self, feature_name: str) -> bool: ...
    def get_feature_config(self, feature_name: str, default: Any = None) -> Any: ...
    
    # Related managers
    api_keys: Manager["ClientAPIKey"]

class ClientDocument(Model):
    objects: Manager[ClientDocument]
    id: AutoField
    client: ForeignKey[Client, Any]
    title: CharField
    file: FileField
    file_type: CharField
    file_size: BigIntegerField
    metadata: JSONField
    is_processed: BooleanField
    processing_error: TextField
    chunks_count: PositiveIntegerField
    uploaded_at: DateTimeField

class ClientEmbedding(Model):
    objects: Manager[ClientEmbedding]
    id: AutoField
    client: ForeignKey[Client, Any]
    document: ForeignKey[ClientDocument, Any]
    embedding_model: ForeignKey[Any, Any]
    vector: Any  # VectorField
    content: TextField
    metadata: JSONField
    created_at: DateTimeField

class ClientAPIConfig(Model):
    objects: Manager[ClientAPIConfig]
    id: AutoField
    client: OneToOneField[Client, Any]
    language: CharField
    integration_type: CharField
    created_at: DateTimeField
    updated_at: DateTimeField

class ClientAPIKey(Model):
    objects: Manager[ClientAPIKey]
    id: AutoField
    client: ForeignKey[Client, Any]
    key: CharField
    name: CharField
    is_active: BooleanField
    rate_limit_per_minute: PositiveIntegerField
    rate_limit_per_day: PositiveIntegerField
    last_used_at: Optional[DateTimeField]
    usage_count: PositiveIntegerField
    created_at: DateTimeField
    expires_at: Optional[DateTimeField]
    
    def is_valid(self) -> bool: ...

class ClientZeroConfig(Model):
    objects: Manager[ClientZeroConfig]
    id: AutoField
    client: OneToOneField[Client, Any]
    enabled: BooleanField
    status: CharField
    image: CharField
    repo_url: CharField
    repo_branch: CharField
    subdomain: CharField
    domain: CharField
    host_port: Optional[PositiveIntegerField]
    container_name: CharField
    container_id: CharField
    db_name: CharField
    db_user: CharField
    db_password: CharField
    db_host: CharField
    db_port: PositiveIntegerField
    better_auth_secret: CharField
    google_client_id: CharField
    google_client_secret: CharField
    autumn_secret_key: CharField
    twilio_account_sid: CharField
    twilio_auth_token: CharField
    twilio_phone_number: CharField
    drop_agent_tables: BooleanField
    thread_sync_max_count: PositiveIntegerField
    thread_sync_loop: BooleanField
    custom_env: JSONField
    last_error: TextField
    created_at: DateTimeField
    updated_at: DateTimeField
    
    @property
    def database_url(self) -> str: ...
    def build_env(self) -> dict[str, str]: ...
