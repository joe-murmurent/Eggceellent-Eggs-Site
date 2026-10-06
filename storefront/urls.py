from django.urls import path

from . import admin_views, views

urlpatterns = [
    path("", views.home, name="home"),
    path("logout/", views.log_out, name="logout"),
    path("password/", views.change_password, name="change_password"),
    path("trip-2027/", views.trip_index, name="trip_index"),
    path("trip-2027/new/", views.create_trip_entry, name="create_trip_entry"),
    path("trip-2027/<int:pk>/", views.trip_entry, name="trip_entry"),
    path("trip-2027/<int:pk>/files/upload/", views.upload_trip_file, name="upload_trip_file"),
    path("trip-2027/<int:pk>/delete/", views.delete_trip_entry, name="delete_trip_entry"),
    path("trip-2027/<int:pk>/files/<int:file_pk>/description/", views.update_file_description, name="update_file_description"),
    path("trip-2027/<int:pk>/files/<int:file_pk>/delete/", views.delete_trip_file, name="delete_trip_file"),
    path("trip-2027/files/<int:pk>/", views.download_trip_file, name="download_trip_file"),
    path("eggs/", views.eggs, name="eggs"),
    path("admin/users/", admin_views.admin_users, name="admin_users"),
    path("admin/roles/", admin_views.admin_roles, name="admin_roles"),
    path("admin/orgs/", admin_views.admin_organizations, name="admin_organizations"),
]
