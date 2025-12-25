"""
URL configuration for task_manager project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # App URLs
    path('', include('apps.accounts.urls', namespace='accounts')),
    path('tasks/', include('apps.tasks.urls', namespace='tasks')),
    path('departments/', include('apps.departments.urls', namespace='departments')),
    path('reports/', include('apps.reports.urls', namespace='reports')),
    path('activity/', include('apps.activity_log.urls', namespace='activity_log')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    
    # Debug toolbar
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns

# Admin site customization
admin.site.site_header = 'Task Manager Administration'
admin.site.site_title = 'Task Manager Admin'
admin.site.index_title = 'Welcome to Task Manager Admin'
