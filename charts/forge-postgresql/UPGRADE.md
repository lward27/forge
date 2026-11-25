# PostgreSQL major-version migration

The primary chart defaults to PostgreSQL 17 and uses the existing
`pgdata-forge-postgresql-0` claim. Never change that image directly to a new
major version: PostgreSQL data files are not compatible across major versions.

The optional `forgePostgresql.migrationTarget` creates a second StatefulSet,
headless Service, and separate PVC. It is disabled by default. The target uses
the version-specific data directory expected by PostgreSQL 18 and does not
select the primary Service until an explicit values change.
Its NetworkPolicy denies egress and accepts ingress only from the Forge
platform Pods or same-namespace migration clients labeled
`maintenance.lucas.engineering/postgresql-client: forge-postgresql-next`.
Confirm the cluster CNI enforces NetworkPolicy before enabling the target.

## Prepare and restore

1. Verify the source Argo application is Synced/Healthy and record its revision,
   source image ID, database names, database owners, extensions, and current
   database health. Confirm storage capacity for both PVCs and the logical
   backup.
2. Enable `forgePostgresql.migrationTarget` with the desired immutable image
   digest. Keep `forgePostgresql.service.primarySelector` at
   `forgePostgresql.name`; do not switch client traffic yet.
3. Quiesce every writer through GitOps and wait for its ready endpoints to
   disappear. Take a fresh full logical backup of every non-template database
   and the cluster globals. The globals dump contains password verifiers and
   the database dumps contain application data: write them to an access
   controlled encrypted backup location, never to logs, a ConfigMap, or the
   repository. Verify archive listings and checksums.
4. Restore globals to the fresh target, omitting only the already initialized
   `postgres` role creation statement; keep its `ALTER ROLE` settings so the
   existing password hash is retained. The target uses the same database
   Secret. Inspect the initialized `forge_platform` database and proceed only
   if it is empty; drop and recreate that empty database with its source owner.
   Abort if it already contains user objects or rows. Create each remaining
   application database with its original owner and restore its custom archive
   with ownership and ACLs enabled. Do not overwrite the image-initialized
   `postgres`, `template0`, or `template1` system databases.
5. Verify PostgreSQL version, extensions, database owners, schema object
   counts, row counts, and application-specific read-only queries on the
   target. Keep the source StatefulSet and PVC intact.

## Cut over and recover

1. With all writers still quiesced through GitOps, set
   `forgePostgresql.service.primarySelector` to
   `forgePostgresql.migrationTarget.name` and set
   `forgePostgresql.replicaCount` to `0`. Keep the migration target enabled.
   Reconcile through Argo CD; do not patch Argo-owned resources directly.
2. Verify the primary Service endpoints select only the ready target Pod,
   perform read-only application checks, then resume writers through GitOps
   and verify application readiness.
3. Before writers resume, rollback is to point the primary Service selector at
   `forgePostgresql.name` and restore its replica count to `1`; the original
   PVC and PostgreSQL 17 data remain intact. After writers resume on PostgreSQL
   18, do not route back to the stale PostgreSQL 17 copy. Preserve a fresh
   PostgreSQL 18 backup and recover forward on the new major version.
4. Keep both PVCs until the migration is accepted and the recovery window has
   passed. Remove the old PVC only with separate explicit authorization.

Use the explicit `lucas_engineering` kube context for bounded observation and
validation. The chart does not create a migration Job or run a dump/restore
automatically.
