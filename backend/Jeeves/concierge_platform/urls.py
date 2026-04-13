from django.urls import path
from rest_framework.routers import DefaultRouter

from Jeeves.concierge_platform import views_owner, views_platform, views_setup
from Jeeves.EmbeddingModel import views_owner as embedding_owner_views
from Jeeves.tools import views_owner as tools_owner_views
from Jeeves.clients import views_owner as clients_owner_views
from Jeeves.branches import views_owner as branches_owner_views

router = DefaultRouter()
router.register(
    r'owner/ai-providers/llm',
    embedding_owner_views.LLMProviderViewSet,
    basename='llm-provider',
)
router.register(
    r'owner/ai-providers/embeddings',
    embedding_owner_views.EmbeddingModelViewSet,
    basename='embedding-model',
)
router.register(
    r'owner/ai-providers/pairs',
    embedding_owner_views.ModelPairViewSet,
    basename='model-pair',
)
router.register(
    r'owner/tools',
    tools_owner_views.ToolCardOwnerViewSet,
    basename='owner-tool',
)
router.register(
    r'owner/clients',
    clients_owner_views.ClientOwnerViewSet,
    basename='owner-client',
)
router.register(
    r'owner/branches',
    branches_owner_views.BranchOwnerViewSet,
    basename='owner-branch',
)

urlpatterns = [
    path('platform/bootstrap/', views_platform.BootstrapView.as_view(), name='platform-bootstrap'),
    path('setup/owner/', views_setup.CreateOwnerView.as_view(), name='setup-owner'),
    path('setup/license/', views_setup.SetupLicenseView.as_view(), name='setup-license'),
    path('setup/complete/', views_setup.SetupCompleteView.as_view(), name='setup-complete'),
    path('owner/dashboard/stats/', views_owner.DashboardStatsView.as_view(), name='owner-dashboard-stats'),
    path('owner/license/reverify/', views_owner.ReverifyLicenseView.as_view(), name='owner-license-reverify'),
    path('owner/settings/defaults/', views_owner.PlatformDefaultsView.as_view(), name='owner-settings-defaults'),
]

urlpatterns += router.urls
