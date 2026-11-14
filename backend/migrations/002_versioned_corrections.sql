-- 002: versioned incremental corrections for pulp datasets, scenario pinning.
-- Fresh databases are created from SQLAlchemy metadata and already include these columns.
-- Existing deployments apply this reviewed migration manually:
ALTER TABLE datasets ADD COLUMN revision INT NOT NULL DEFAULT 1;
ALTER TABLE scenarios ADD COLUMN dataset_revision INT NOT NULL DEFAULT 1;
ALTER TABLE scenarios ADD COLUMN materials_snapshot JSON NULL;
-- Pin pre-existing scenarios to their dataset's current materials so later corrections
-- do not change what those scenarios compute:
UPDATE scenarios s JOIN datasets d ON d.id=s.dataset_id
 SET s.materials_snapshot=d.materials, s.dataset_revision=d.revision
 WHERE s.materials_snapshot IS NULL;
-- Material rows stored before this change carry no per-row version; the application
-- treats a missing version as 1, so no JSON backfill is required.
