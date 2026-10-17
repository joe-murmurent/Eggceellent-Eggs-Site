# Data Dictionary

This document describes the schema in `db.sqlite3`, based on the Django models and the SQLite database inspected on 2026-10-17. It documents structure only; it does not contain database records or credentials.

After applying the current migrations, the database contains 15 application and Django-managed tables. Five `storefront_*` tables hold site data. The remaining tables support Django authentication, authorization, sessions, migrations, and admin logging.

## Relationships

| Parent | Child | Relationship | Behavior |
| --- | --- | --- | --- |
| `storefront_tripentry.id` | `storefront_tripentryfile.trip_entry_id` | One trip entry has zero or more files | Django ORM cascades file-row deletion when its trip entry is deleted. |
| `auth_user.id` | `auth_user_groups.user_id` | Users can belong to multiple groups | Many-to-many through table. |
| `auth_group.id` | `auth_user_groups.group_id` | Groups can contain multiple users | Many-to-many through table. |
| `auth_user.id` | `auth_user_user_permissions.user_id` | Users can have direct permissions | Many-to-many through table. |
| `auth_permission.id` | `auth_user_user_permissions.permission_id` | A permission can be assigned to multiple users | Many-to-many through table. |
| `auth_group.id` | `auth_group_permissions.group_id` | Groups can have multiple permissions | Many-to-many through table. |
| `auth_permission.id` | `auth_group_permissions.permission_id` | A permission can belong to multiple groups | Many-to-many through table. |
| `django_content_type.id` | `auth_permission.content_type_id` | Each permission describes a model permission | Django-managed foreign key. |
| `auth_user.id` | `django_admin_log.user_id` | Each admin log entry has an actor | Django-managed foreign key. |
| `django_content_type.id` | `django_admin_log.content_type_id` | An admin log entry may refer to a model type | Nullable Django-managed foreign key. |

The seeded groups include `ADMIN`, `USER`, `VIEWER`, and `EGGS`. `ADMIN` controls administration pages; `EGGS` grants access to the EGGS area.

## Site Data

### `storefront_organization`

Organization/contact information. All business detail fields are optional.

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Django `BigAutoField` identifier. |
| `business_name` | TEXT | Yes | | Organization or business name. |
| `street_address` | TEXT | Yes | | Street address. |
| `city` | TEXT | Yes | | City or locality. |
| `state` | TEXT | Yes | | State or region. |
| `postal_code` | TEXT | Yes | | Postal or ZIP code. |
| `business_type` | TEXT | Yes | | Type of business. |
| `business_start_date` | date | Yes | | Business start date. |
| `license` | TEXT | Yes | | License information. |
| `registration_number` | TEXT | Yes | | Registration identifier. |

### `storefront_tripentry`

One journal entry for a trip event.

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Django `BigAutoField` identifier. |
| `event_date` | date | No | | Event date. |
| `event_title` | TEXT | No | | Event title. |
| `event_description` | TEXT | Yes | | Optional event description. |
| `geo_location` | varchar(64) | No | | Optional map coordinate pair stored as `latitude, longitude`; validated to latitude -90 through 90 and longitude -180 through 180. |

Entries are ordered by event date descending, then identifier descending. Coordinates are stored as `latitude, longitude` and rendered on the OpenFreeMap route map.

### `storefront_itinerarystop`

One destination in the 2027 RV itinerary. Stops retain the workbook's dates, campground options, travel details, booking notes, activities, weather, and towing notes. The admin-only Itinerary Planner also stores an optional coordinate pair for mapping each destination.

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Django `BigAutoField` identifier. |
| `day_number` | smallint unsigned | No | | Day number from the itinerary workbook. |
| `stop_date` | date | No | | Date used to order the destination. |
| `destination` | varchar(180) | No | | Destination name and region. |
| `preferred_campground` | varchar(200) | No | | First-choice campground. |
| `alternate_campground` | varchar(200) | No | | Alternate campground. |
| `check_in`, `check_out` | date | Yes | | Planned campground dates. |
| `route`, `drive_time` | varchar | No | | Route description and estimated drive duration. |
| `site_type`, `booking_requirements` | varchar/text | No | | RV site and booking or hookup notes. |
| `price_or_membership` | varchar(100) | No | | Workbook cost estimate or membership note. |
| `booking_opening_estimate` | varchar(80) | No | | Estimated reservation opening date from the workbook. |
| `attractions`, `landscape`, `fuel_errands` | text/varchar | No | | Activities, landscape/water notes, and fuel/errands. |
| `stop_category`, `weather`, `towing_notes` | varchar/text | No | | Stop type, seasonal notes, and towing guidance. |
| `booking_status` | varchar(40) | No | | Workbook status such as `BOOK`, `WAIT`, or `FINAL`. |
| `geo_location` | varchar(64) | No | | Optional coordinate pair validated to latitude -90 through 90 and longitude -180 through 180. |

Stops are ordered by `stop_date`, then `day_number`, then identifier.

### `storefront_itineraryreference`

Planning assumptions and source references imported from the workbook's `Planning Notes` and `Sources` sheets.

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Django `BigAutoField` identifier. |
| `reference_type` | varchar(20) | No | | Either `assumption` or `source`. |
| `title` | varchar(200) | No | | Assumption title or source name. |
| `detail` | TEXT | No | | Planning note or source purpose. |
| `url` | varchar(200) | No | | Optional source URL. |
| `display_order` | smallint unsigned | No | | Workbook display order. |

### `storefront_tripentryfile`

File metadata associated with a trip entry. The file contents are stored on the media filesystem; `file` stores a relative path, not a database blob.

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Django `BigAutoField` identifier. |
| `trip_entry_id` | BIGINT | No | FK | References `storefront_tripentry.id`; indexed. |
| `file` | varchar(100) | No | | Relative media path, stored under `trip_2027_files/images/`, `videos/`, or `other/`. |
| `file_name` | TEXT | No | | Original/display filename. |
| `file_type` | TEXT | No | | MIME type recorded for the upload. |
| `description` | TEXT | Yes | | Optional file description. |

The Django model declares `on_delete=CASCADE` and exposes related files as `TripEntry.files`.

## Accounts and Permissions

These tables are managed by Django's authentication framework. Password values in `auth_user.password` are encoded password hashes.

### `auth_user`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | User identifier. |
| `password` | varchar(128) | No | | Encoded password hash. |
| `last_login` | datetime | Yes | | Most recent login time. |
| `is_superuser` | bool | No | | Grants all permissions. |
| `username` | varchar(150) | No | UNIQUE | Unique login name. |
| `last_name` | varchar(150) | No | | Last name. |
| `email` | varchar(254) | No | | Email address. |
| `is_staff` | bool | No | | Django admin-site staff flag. |
| `is_active` | bool | No | | Whether the account is active. |
| `date_joined` | datetime | No | | Account creation time. |
| `first_name` | varchar(150) | No | | First name. |

### `auth_group`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Group identifier. |
| `name` | varchar(150) | No | UNIQUE | Role/group name. |

### `auth_permission`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Permission identifier. |
| `content_type_id` | INTEGER | No | FK | References `django_content_type.id`; indexed. |
| `codename` | varchar(100) | No | UNIQUE with `content_type_id` | Permission codename. |
| `name` | varchar(255) | No | | Human-readable permission name. |

### `auth_user_groups`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Join-row identifier. |
| `user_id` | INTEGER | No | FK | References `auth_user.id`; indexed. |
| `group_id` | INTEGER | No | FK | References `auth_group.id`; indexed. |

The pair (`user_id`, `group_id`) is unique.

### `auth_user_user_permissions`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Join-row identifier. |
| `user_id` | INTEGER | No | FK | References `auth_user.id`; indexed. |
| `permission_id` | INTEGER | No | FK | References `auth_permission.id`; indexed. |

The pair (`user_id`, `permission_id`) is unique.

### `auth_group_permissions`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Join-row identifier. |
| `group_id` | INTEGER | No | FK | References `auth_group.id`; indexed. |
| `permission_id` | INTEGER | No | FK | References `auth_permission.id`; indexed. |

The pair (`group_id`, `permission_id`) is unique.

## Django Support Tables

### `django_content_type`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Content-type identifier. |
| `app_label` | varchar(100) | No | UNIQUE with `model` | Django app label. |
| `model` | varchar(100) | No | UNIQUE with `app_label` | Lowercase model name. |

The pair (`app_label`, `model`) is unique.

### `django_admin_log`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Log entry identifier. |
| `action_time` | datetime | No | | Time of the action. |
| `object_id` | TEXT | Yes | | String form of the affected object's identifier. |
| `object_repr` | varchar(200) | No | | Display representation of the object. |
| `action_flag` | smallint unsigned | No | | Django admin action code. |
| `change_message` | TEXT | No | | Description of the change. |
| `content_type_id` | INTEGER | Yes | FK | References `django_content_type.id`; indexed. |
| `user_id` | INTEGER | No | FK | References `auth_user.id`; indexed. |

### `django_migrations`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `id` | INTEGER | No | PK | Migration-row identifier. |
| `app` | varchar(255) | No | | Django app label. |
| `name` | varchar(255) | No | | Migration name. |
| `applied` | datetime | No | | When the migration was applied. |

### `django_session`

| Column | SQLite type | Null | Key | Description |
| --- | --- | --- | --- | --- |
| `session_key` | varchar(40) | No | PK | Session identifier. |
| `session_data` | TEXT | No | | Encoded session data. |
| `expire_date` | datetime | No | INDEX | Session expiration time. |

## Notes

- The field definitions follow the Django models and the current SQLite database. Recheck this document after model changes or migrations.
- SQLite's declared foreign keys use `NO ACTION`; Django applies model `on_delete` behavior through its ORM deletion collector.
- Uploaded file bytes live under `MEDIA_ROOT`; only the relative path and metadata are stored in SQLite.