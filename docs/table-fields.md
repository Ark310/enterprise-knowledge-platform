# TD schema review guide v0.3.0
29 tables; 301 columns; 55 foreign-key constraints.

## knowledge.source_groups
The two source roots and their evidence roles. Tracks Drive scanning without treating folder membership as proof of truth.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| group_key | text | yes | Stable application key for the source root, for example current-state or existing-assets. |
| evidence_role | text | yes | Classifies the root as CURRENT_STATE or EXISTING_ASSET; neither value automatically establishes factual truth. |
| drive_folder_id | text | yes | Google Drive folder ID for this root. Unique across registered roots. |
| folder_url | text | yes | Original human-facing Drive folder link. |
| sync_cursor | text | no | Opaque Drive change-feed token for a later incremental sync; not a file revision or content hash. |
| last_successful_scan_at | timestamptz | no | Time the application last completed and committed a successful scan of this root. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |

Keys: PK (id); UNIQUE (group_key); UNIQUE (drive_folder_id); UNIQUE (id, evidence_role)
Rules: The group evidence role constrains source_versions through a composite FK. Folder role is provenance classification, not a trust score.
## knowledge.storage_objects
A physical Drive file or a member inside an archive. Keeps stable file identity apart from individual revisions.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| group_id | uuid | yes | The registered source root owning this physical object. An archive member must have the same group as its parent. |
| object_key | text | yes | Idempotent physical-object key within the root. Use stable Drive identity or parent/member identity rather than the display title alone. |
| object_kind | text | yes | DRIVE_FILE for an externally stored file, or ARCHIVE_MEMBER for a member inside an archive. |
| drive_file_id | text | no | Drive ID. Required for a DRIVE_FILE and absent for an ARCHIVE_MEMBER. |
| parent_object_id | uuid | no | Physical parent archive object. Required for an ARCHIVE_MEMBER and absent for a DRIVE_FILE. |
| member_path | text | no | Full member path inside the archive. Required for an ARCHIVE_MEMBER; keep it distinct from an extraction destination on disk. |
| title | text | yes | Human-readable title or filename used for display and discovery. |
| mime_type | text | no | Declared format, such as application/pdf or video/mp4; preserve the original format identity. |
| original_url | text | no | Original provider link to the physical file. A ZIP member may rely on its parent archive link and member path. |
| availability | text | yes | Whether the physical object is currently available, trashed, missing or inaccessible. This is separate from extraction success. |
| last_seen_at | timestamptz | yes | Last time the object was observed during discovery. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |
| detected_mime_type | text | no | Format detected from file bytes, separately from the original name or provider-declared MIME type. |
| format_details | jsonb | yes | Detected format attributes or signature evidence, such as image dimensions and a proprietary capture format identifier. |

Keys: PK (id); UNIQUE (group_id, object_key); UNIQUE (id, group_id)
Rules: Conditional fields: DRIVE_FILE requires drive_file_id and forbids parent/member fields; ARCHIVE_MEMBER requires parent_object_id and member_path and forbids drive_file_id. Parent and child must share a source group.
## knowledge.object_versions
An exact physical file/member revision, with checksums and archive ancestry so citations can resolve the original bytes.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| object_id | uuid | yes | The physical object whose revision this is. |
| version_key | text | yes | Idempotent revision key within the physical object; derived from provider revision and/or verified content/parent-version evidence. |
| provider_revision | text | no | Provider-supplied revision/version label, if available. Not necessarily a checksum. |
| provider_modified_at | timestamptz | no | Modification timestamp reported by the provider; not proof of product currency. |
| byte_size | bigint | no | Actual byte length when known; must be zero or greater. |
| sha256 | text | no | Lowercase 64-character SHA-256 fingerprint of the actual bytes; unknown until the bytes are available. |
| parent_archive_version_id | uuid | no | The exact physical archive revision containing this member. Absent for a top-level Drive file. |
| archive_entry_index | integer | no | Zero-based central-directory entry index inside the pinned archive revision. Paired with parent_archive_version_id. |
| crc32 | text | no | Archive member CRC value, used for integrity checks in addition to SHA-256. |
| registered_at | timestamptz | yes | Time this physical revision was registered in the database. |
| storage_uri | text | no | Private durable location/reference for this representation. Do not store a temporary signed download URL here. |
| read_status | text | yes | Registration/readability result, such as READABLE, SIZE_BLOCKED or CORRUPT; not an article coverage assessment. |
| error_details | jsonb | yes | Structured reason why reading this physical revision failed or was blocked. |

Keys: PK (id); UNIQUE (object_id, version_key)
Rules: For archive members, the lineage trigger requires a parent archive revision belonging to the declared parent object. Parent archive version and entry index are paired. Hashes may be unknown at metadata-only registration.
## knowledge.intake_batches
A declared discovery batch and its inventory reconciliation result. A complete scan can still include declared exclusions.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| batch_key | text | yes | Unique application key identifying this discovery/intake batch. |
| manifest_object_version_id | uuid | no | Exact physical version of the control inventory/workbook, if one was supplied and registered. |
| declared_scope | jsonb | yes | What this batch claims to cover: roots, archive parts, categories and relevant scope limitations. |
| discovered_at | timestamptz | yes | Time this intake batch was recorded. |
| scan_status | text | yes | Progress/result of the scan itself, independently of whether all expected content was supplied. |
| manifest_reconciliation | text | yes | Whether the observed supplied parts match the manifest, mismatch it, were not checked or have no manifest. |
| notes | jsonb | yes | Supplementary batch-level observations, counts and limitations. |

Keys: PK (id); UNIQUE (batch_key)
Rules: MATCHES_SUPPLIED_PARTS means the supplied parts reconcile; it does not erase manifest-declared exclusions.
## knowledge.intake_entries
One expected inventory entry, including files that were supplied, excluded, missing or unreadable.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| batch_id | uuid | yes | The intake batch containing this declared inventory entry. |
| group_id | uuid | yes | Source root/category to which this expected item belongs. |
| entry_key | text | yes | Idempotent entry key within the batch; it must distinguish any otherwise ambiguous repeated paths. |
| container_name | text | no | Declared archive/part name, where applicable. |
| member_path | text | yes | Declared item path, even if the bytes were excluded or unavailable. |
| expected_bytes | bigint | no | Expected exact byte length, only when the manifest supplies it. Do not convert rounded MB values into invented exact bytes. |
| expected_sha256 | text | no | Expected content hash supplied by a trusted manifest, if available; distinct from a newly observed hash. |
| observed_object_version_id | uuid | no | Actual registered physical revision observed for this entry. Required when presence_status is PRESENT. |
| presence_status | text | yes | PRESENT, EXCLUDED, MISSING or UNREADABLE. An exclusion is recorded without inventing ingested evidence. |
| review_status | text | yes | Depth/state of inspection, from INVENTORIED through CONTENT_REVIEWED or a conversion/blocking state. |
| reason | text | no | Explanation required when the entry is not PRESENT; may additionally explain limitations for a present item. |
| details | jsonb | yes | Supplementary structured details that do not have their own typed column. |

Keys: PK (id); UNIQUE (batch_id, entry_key)
Rules: PRESENT requires an observed physical revision. Every non-PRESENT entry requires a reason. Detailed review depth is independent of presence.
## knowledge.ingestion_jobs
One processing attempt for a physical version. Records failures and conversions independently of documentation coverage.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| object_version_id | uuid | yes | The exact physical file/member version used by this row. |
| operation | text | yes | Processing action, such as ENUMERATE, CONVERT, EXTRACT, OCR, TRANSCRIBE, CHUNK, EMBED or VALIDATE. |
| processor_version | text | yes | Version of the extractor, converter or other processing implementation. |
| config_sha256 | text | yes | Fingerprint of the exact processing configuration, so changed settings can create a distinct result. |
| attempt | integer | yes | Positive retry number for this physical version/action/processor/configuration combination. |
| status | text | yes | Processing state/result: pending, running, complete, partial, blocked or failed. |
| started_at | timestamptz | no | Time this attempt started, if it has started. |
| finished_at | timestamptz | no | Time this attempt finished, if it has finished. |
| error_details | jsonb | yes | Structured errors or reasons for blocked/partial processing. |

Keys: PK (id); UNIQUE (object_version_id, operation, processor_version, config_sha256, attempt)
## knowledge.sources
A logical knowledge item, such as one article, endpoint page, recording, transcript or workbook. Several files can represent one source.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| source_system | text | yes | Originating system, such as a Confluence site or API documentation export. Part of logical identity. |
| external_key | text | yes | Stable upstream identifier, such as an article/page ID; not simply a display title. |
| source_type | text | yes | Logical content kind, such as ARTICLE, RECORDING, DOCUMENT, API_REFERENCE or EDITABLE_CAPTURE. The physical format is stored separately. |
| title | text | yes | Human-readable title or filename used for display and discovery. |
| product | text | no | Explicit product/category key when known. Nullable and has no default TD classification in v0.3.0. |
| module | text | no | Product module or functional area; do not infer an unknown module merely from a nearby filename. |
| source_url | text | no | Original logical article/reference URL, which may differ from the Drive location holding its export. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |
| external_namespace | text | yes | Scope for the upstream identifier, such as site/space or export namespace, to prevent ID collisions across systems. |

Keys: PK (id); UNIQUE (source_system, external_namespace, external_key)
## knowledge.source_versions
A specific logical-source revision and its product/configuration applicability. Separate from the physical file revision.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| source_id | uuid | yes | The stable logical knowledge item whose revision this is. |
| revision_key | text | yes | Idempotent revision key for this logical source. Preserve upstream revision plus the representation-manifest fingerprint where needed. |
| evidence_role | text | yes | CURRENT_STATE or EXISTING_ASSET for this revision. Must agree with the registered source group. |
| storage_uri | text | yes | Original location/reference used to recover this revision; detailed physical exports are linked through version_representations. |
| object_version_id | text | no | Optional external storage-version label stored as TEXT. This legacy-named field is NOT a UUID foreign key to knowledge.object_versions. |
| mime_type | text | yes | Primary representation format recorded for this logical revision; alternate formats remain linked separately. |
| byte_size | bigint | no | Actual byte length when known; must be zero or greater. |
| content_sha256 | text | no | Fingerprint of the chosen logical content representation, when actually computed; do not invent it at metadata-only registration. |
| external_revision | text | no | Original upstream article/document revision label, if known. |
| source_modified_at | timestamptz | no | Upstream modification timestamp, not the ingestion timestamp and not automatic proof of current behavior. |
| ingested_at | timestamptz | yes | Time the logical source revision was registered/ingested locally. |
| lifecycle_status | text | yes | ACTIVE, SUPERSEDED or DELETED. An explicit lifecycle selection, not an automatic newest-file-is-true rule. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |
| applicability | jsonb | yes | Known product build, environment, role and configuration scope. Unknown applicability remains unknown. |
| group_id | uuid | yes | The source root under which this revision is classified. Required in the final v0.3.0 SQL. |

Keys: PK (id); UNIQUE (source_id, revision_key); UNIQUE (id, source_id)
Rules: group_id and evidence_role must match the referenced group. content_sha256 is nullable in the final SQL. object_version_id is a text label; physical UUID links belong in version_representations.
## knowledge.version_representations
A bridge connecting a logical revision to physical exports, attachments, transcripts or screenshots.

| Field | Type | Required | Meaning |
|---|---|---|---|
| source_version_id | uuid | yes | The exact logical-source revision to which this row belongs. |
| object_version_id | uuid | yes | The exact physical file/member version used by this row. |
| representation_role | text | yes | How the physical file represents the logical revision: PRIMARY, ALTERNATE_EXPORT, ATTACHMENT, TRANSCRIPT or SCREENSHOT. |
| metadata | jsonb | yes | Representation-specific context, such as API reference versus Try It, code language or original export naming. |

Keys: PK (source_version_id, object_version_id); CREATE UNIQUE INDEX primary_representation_idx ON knowledge.version_representations (source_version_id) WHERE representation_role = 'PRIMARY'
Rules: At most one PRIMARY physical representation per logical revision, enforced by a partial unique index. Other representations can coexist.
## knowledge.source_links
A reference from a source revision to another source or an unresolved target, such as a guide linked by a release note.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| from_version_id | uuid | yes | Source revision containing the reference or relationship. |
| to_source_id | uuid | no | Resolved logical target, if identified. A RESOLVED link must identify this target. |
| target_uri | text | yes | Original linked target/reference, preserved even when the target has not been supplied. |
| relationship | text | yes | Named relationship, such as a reference to a guide or an attachment/transcript association. This text field is not a fixed enum. |
| resolution_status | text | yes | RESOLVED, UNRESOLVED or UNAVAILABLE; keeps a referenced-but-unavailable guide visible. |
| to_version_id | uuid | no | Optional exact target revision. If supplied, it must belong to to_source_id through the composite foreign key. |

Keys: PK (id); UNIQUE (from_version_id, target_uri, relationship)
Rules: RESOLVED requires to_source_id. An optional to_version_id must identify a revision of that target source; unresolved links preserve the original URI.
## knowledge.extractions
One versioned extraction result for a logical revision. The selected active result is explicit; older attempts remain available.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| source_version_id | uuid | yes | The exact logical-source revision to which this row belongs. |
| method | text | yes | Extraction method, such as native text parsing, subtitle parsing, OCR or transcript generation. |
| processor_version | text | yes | Version of the extractor, converter or other processing implementation. |
| status | text | yes | PENDING, PROCESSING, COMPLETE, PARTIAL or FAILED for this extraction result. |
| warnings | jsonb | yes | JSON warning list by convention, including incomplete pages, uncertain timing or unsupported portions. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |
| config_sha256 | text | no | Fingerprint of the exact processing configuration, so changed settings can create a distinct result. |
| is_active | boolean | yes | Selects the extraction used by normal retrieval. At most one selected extraction per source revision; only COMPLETE/PARTIAL may be selected. |
| input_artifact_id | uuid | no | Optional derived artifact consumed by this extraction, for example OCR reading a native image export. Must belong to the same source revision. |

Keys: PK (id); UNIQUE (id, source_version_id); CREATE UNIQUE INDEX active_extraction_idx ON knowledge.extractions (source_version_id) WHERE is_active
Rules: A partial unique index permits at most one is_active=true row per source revision. A selected extraction must be COMPLETE or PARTIAL. Input artifacts must belong to the same source revision.
## knowledge.artifacts
A derived representation such as an image export, video frame, transcript, converted document or structured intermediate result.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| source_version_id | uuid | yes | The exact logical-source revision to which this row belongs. |
| extraction_id | uuid | yes | The extraction result that produced or owns this row. |
| origin_object_version_id | uuid | no | Exact physical member/file from which the representation originated, when applicable. |
| parent_artifact_id | uuid | no | Optional preceding artifact in the derivation chain, such as the image that OCR read. Must belong to the same source revision. |
| artifact_key | text | yes | Idempotent artifact identifier within one extraction result. |
| artifact_kind | text | yes | Representation kind: text, rendered image, frame, transcript, structured data, converted document or transcoded media. |
| mime_type | text | yes | Declared format, such as application/pdf or video/mp4; preserve the original format identity. |
| storage_uri | text | no | Private durable location/reference for this representation. Do not store a temporary signed download URL here. |
| inline_data | jsonb | no | Optional bounded structured representation stored directly as JSON; large binary artifacts remain outside the database. |
| sha256 | text | no | Lowercase 64-character SHA-256 fingerprint of the actual bytes; unknown until the bytes are available. |
| status | text | yes | Whether the derived representation is pending, ready, empty, blocked, failed or unavailable. |
| locator | jsonb | yes | Original source position represented by this artifact, such as a frame timestamp or document page. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |

Keys: PK (id); UNIQUE (extraction_id, artifact_key); UNIQUE (id, source_version_id)
Rules: The extraction and parent artifact must belong to the same source revision. READY requires a hash and at least a storage URI or inline JSON representation. Readiness is not a claim that OCR or interpretation is correct.
## knowledge.content_units
A citable text unit for search and analysis: a section, paragraph, cell range, subtitle cue, OCR result or code example.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| extraction_id | uuid | yes | The extraction result that produced or owns this row. |
| parent_unit_id | uuid | no | Optional parent section/unit from the same extraction, supporting document hierarchy. |
| unit_key | text | yes | Idempotent section/chunk identifier within the extraction. |
| unit_type | text | yes | Unit subtype, such as section, paragraph, spreadsheet range, caption cue or code block. This is a free-text classification. |
| heading | text | no | Optional section/chunk heading for display and search context. |
| content_text | text | yes | The exact extracted or generated text represented by this unit; provenance distinguishes its origin. |
| representation_kind | text | yes | SOURCE_TEXT, SUPPLIED_TRANSCRIPT, GENERATED_TRANSCRIPT, OCR or GENERATED_DESCRIPTION. Prevents generated text from masquerading as original evidence. |
| locator | jsonb | yes | Structured citation position, such as page, paragraph, line range, cell range, image coordinates or video time. |
| content_sha256 | text | yes | Fingerprint of this content unit text/representation, used to detect changes and support reproducible processing. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |
| search_text | tsvector | computed | Database-generated full-text-search tokens from heading plus content_text, using the simple text-search configuration. |
| artifact_uri | text | no | Optional direct representation URI retained from the earlier draft. artifact_id is the structured derivative link when available. |
| start_seconds | numeric | no | Optional start offset in the original recording, in seconds; zero is valid. |
| end_seconds | numeric | no | Optional end offset; if present, a start is required and end must not precede start. |
| page_number | integer | no | Optional one-based document/PDF page number. |
| sheet_name | text | no | Optional spreadsheet worksheet name for a cited range. |
| cell_range | text | no | Optional A1-style cell range, such as A1:G20; parsing/validation is an application responsibility. |
| artifact_id | uuid | no | Optional derived artifact represented by this unit; links text to its frame/render/transcript/structured origin. |
| language | text | no | Programming language for code chunks or human language for prose/transcripts, with the context retained in unit metadata. |
| content_status | text | yes | USABLE, EMPTY, UNVERIFIED or REDACTED. Normal active-content retrieval excludes non-USABLE or whitespace-only text. |

Keys: PK (id); UNIQUE (extraction_id, unit_key); UNIQUE (id, extraction_id)
Rules: Parent units must share the extraction. end_seconds requires start_seconds and cannot precede it; pages must be positive. The active view excludes non-USABLE/blank text and non-ready linked artifacts. The app must additionally check applicability/access and artifact-source consistency.
## knowledge.unit_links
A relationship between two content units, such as a screenshot illustrating a paragraph or a transcript describing a recording segment.

| Field | Type | Required | Meaning |
|---|---|---|---|
| from_unit_id | uuid | yes | Content unit from which the relationship is stated. |
| to_unit_id | uuid | yes | Target content unit, which must differ from the source unit. |
| relationship | text | yes | ILLUSTRATES, TRANSCRIBES, DERIVED_FROM, NEXT or ATTACHMENT. |
| details | jsonb | yes | Supplementary structured details that do not have their own typed column. |

Keys: PK (from_unit_id, to_unit_id, relationship)
## knowledge.media_tracks
Technical metadata for a video, audio or subtitle stream. Does not claim that its contents have been semantically verified.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| source_version_id | uuid | yes | The exact logical-source revision to which this row belongs. |
| stream_index | integer | yes | Zero-based stream index reported by the media probe; unique within the logical source revision. |
| track_type | text | yes | VIDEO, AUDIO, SUBTITLE, DATA or OTHER. |
| codec | text | no | Codec name reported for this stream, such as h264 or wmv3. |
| duration_seconds | numeric | no | Duration reported for this stream, when known; not a statement that it has been watched or listened to. |
| width | integer | no | Video/image stream width in pixels, when applicable. |
| height | integer | no | Video/image stream height in pixels, when applicable. |
| sample_rate | integer | no | Audio samples per second, when applicable. |
| channels | integer | no | Number of audio channels, when applicable. |
| frame_rate_numerator | bigint | no | Numerator of the reported rational frame rate; preserve it with the denominator instead of rounding. |
| frame_rate_denominator | bigint | no | Positive denominator of the reported rational frame rate. |
| language | text | no | Language label reported or assigned for this stream, if known. |
| time_base | text | no | Raw stream timebase used to interpret timestamps; seconds-based citation conversion must retain this provenance. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |

Keys: PK (id); UNIQUE (source_version_id, stream_index)
Rules: Stream index is unique within a source revision. Width/height/sample rate/channels/denominator must be positive if supplied; duration cannot be negative. Applicability to audio/video/subtitle tracks is an application convention.
## knowledge.api_operations
A versioned documentary description of an API operation. This is not a live API execution registry.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| source_version_id | uuid | yes | The exact logical-source revision to which this row belongs. |
| operation_key | text | yes | Idempotent operation key within this source revision. Global method/path uniqueness is deliberately not required. |
| method_raw | text | yes | HTTP method exactly as documented, such as GET or POST. |
| path_raw | text | yes | Endpoint path exactly as documented, including unusual formatting; do not silently repair it. |
| request_url_raw | text | no | Captured full request URL, when supplied by the reference/runner export. |
| audience_label | text | no | Documented audience context, such as TD user versus web user, if established. |
| environment_label | text | no | Documented environment context, such as sandbox, only when supported by the source. |
| api_version_label | text | no | Documented API version label; distinct from the database source revision. |
| source_locator | jsonb | yes | Position in the originating documentation, typically a JSON pointer, member path or section locator. |
| raw_definition | jsonb | yes | The unmodified structured definition from the source export, retained alongside extracted typed fields. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |

Keys: PK (id); UNIQUE (source_version_id, operation_key)
Rules: The unique key is (source_version_id, operation_key), not global (method_raw,path_raw). Raw endpoint identity and documented claims remain attributable to their source revision.
## knowledge.api_examples
A captured request, response, code snippet or Try It representation belonging to an operation.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| operation_id | uuid | yes | The versioned API operation to which this row belongs. |
| example_key | text | yes | Idempotent example key within an operation, distinguishing language, context and response variants. |
| example_kind | text | yes | REQUEST, RESPONSE, CODE_SAMPLE or TRYIT_CAPTURE. A capture is not proof of an executed request. |
| context | text | yes | REFERENCE, TRYIT or OTHER source context; reference and runner examples must remain distinguishable. |
| language | text | no | Programming language of a code example, such as C#, Python or shell/cURL. |
| status_label_raw | text | no | Exact documented response label, including anomalous values such as 20, 2011 or 200 (Status=True). |
| http_status | integer | no | Optional independently validated numeric HTTP status between 100 and 599. Never silently coerce an anomalous raw label. |
| content_type | text | no | Documented/captured response or request MIME type, when known. |
| body_text | text | no | Captured plain-text body or code snippet, preserved without executing it. |
| structured_body | jsonb | no | Optional parsed JSON body alongside the source text; keep exact source fidelity where parsing loses formatting. |
| payload_status | text | yes | PRESENT, EMPTY, NOT_CAPTURED or UNREADABLE. Distinguishes a zero-byte capture from an absent example. |
| source_object_version_id | uuid | no | Exact physical example/snippet file revision from the archive, if one exists. |
| content_unit_id | uuid | no | Optional citable evidence chunk containing this example. |
| source_locator | jsonb | yes | Position in the originating documentation, typically a JSON pointer, member path or section locator. |
| metadata | jsonb | yes | Additional provenance or format attributes for this row; use typed columns for fields needed in exact queries. |

Keys: PK (id); UNIQUE (operation_id, example_key); UNIQUE (id, operation_id)
Rules: Only RESPONSE examples may carry response status fields. Numeric http_status, if populated, must be 100-599. Raw status labels are preserved separately; capture/execution semantics remain distinct.
## knowledge.api_parameters
A documented parameter tree, preserving header/path/query/body/response context and the original required/type claims.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| operation_id | uuid | yes | The versioned API operation to which this row belongs. |
| response_example_id | uuid | no | For a RESPONSE parameter, the response example/variant it belongs to. Required by a conditional check for RESPONSE location. |
| parent_parameter_id | uuid | no | Optional parent parameter in the same operation and location, preserving nested object/array structure. |
| parameter_key | text | yes | Idempotent parameter key within the operation, normally including its full source pointer/context so repeated names do not collide. |
| location | text | yes | HEADER, PATH, QUERY, BODY or RESPONSE location in the documented operation. |
| name | text | yes | Parameter name exactly as documented. |
| data_type_raw | text | no | Documented type label; not a claim that the live API validates this type. |
| required_claim | boolean | no | Nullable documented required/not-required claim. False or null is not execution proof that the field can be omitted. |
| description | text | no | Documented explanation of the parameter. |
| example_value | jsonb | no | Optional example value represented as JSON, preserving scalar/object/array structure. |
| ordinal | integer | yes | Zero-based ordering value preserving parameter order in its original context. |
| source_locator | jsonb | yes | Position in the originating documentation, typically a JSON pointer, member path or section locator. |
| raw_definition | jsonb | yes | The unmodified structured definition from the source export, retained alongside extracted typed fields. |

Keys: PK (id); UNIQUE (operation_id, parameter_key); UNIQUE (id, operation_id, location)
Rules: Nested parents must belong to the same operation and location. A RESPONSE parameter requires response_example_id, and that example must belong to the same operation. The app must keep nested response-context assignments consistent.
## analysis.runs
One scoped documentation-review question, including module/topic and the contract/instruction versions in use.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| run_key | text | yes | Unique application identifier for this review/test run. |
| module | text | yes | Product module or functional area; do not infer an unknown module merely from a nearby filename. |
| topic | text | yes | The specific topic being reviewed or described. |
| question | text | yes | The concrete review question that defines the run scope. |
| contract_version | text | yes | Version of the structured A/B message contract used for this run. |
| agent_a_version | text | yes | Instruction/version identifier used by Agent A. |
| agent_b_version | text | yes | Instruction/version identifier used by Agent B. |
| status | text | yes | Run-level progress/result; separate from any individual extraction, output validation or human decision. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |
| completed_at | timestamptz | no | Time the run completed, if it has completed. |

Keys: PK (id); UNIQUE (run_key)
Rules: Pipeline ordering is not enforced by this row alone; the application must gate stages using the declared evidence scope.
## analysis.stages
An attempt at one stage of a review pipeline. This is an audit ledger; application logic must enforce readiness and ordering.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| run_id | uuid | yes | The scoped review run to which this row belongs. |
| stage | text | yes | SOURCE_EMBED, AGENT_A, A_EMBED, AGENT_B, B_EMBED or RETRIEVAL_READY stage. |
| attempt | integer | yes | Positive attempt number for this run/stage. |
| status | text | yes | Stage progress/result, including PARTIAL or BLOCKED when applicable. |
| profile_id | uuid | no | Embedding profile associated with the stage, if relevant; the SQL does not require it on every stage. |
| started_at | timestamptz | no | Time this stage attempt started. |
| completed_at | timestamptz | no | Time this stage attempt completed. |
| details | jsonb | yes | Stage manifest, counts, blockers and selected evidence context. Application logic must verify readiness before advancing. |

Keys: PK (id); UNIQUE (run_id, stage, attempt)
## analysis.run_sources
The exact source revisions searched or reviewed for a run, with the scope and depth of that coverage.

| Field | Type | Required | Meaning |
|---|---|---|---|
| run_id | uuid | yes | The scoped review run to which this row belongs. |
| source_version_id | uuid | yes | The exact logical-source revision to which this row belongs. |
| coverage_status | text | yes | LISTED, SEARCHED, REVIEWED, PARTIAL or UNREADABLE. A search hit is not a detailed review. |
| coverage_details | jsonb | yes | Coverage evidence and selected content/extraction IDs by application convention. |
| search_terms | jsonb | yes | JSON list of search terms/aliases used, by convention; preserve what was actually searched. |
| reviewed_scope | jsonb | yes | Actual sections, time ranges, cells or topics reviewed; prevents a narrow review from certifying a whole source. |

Keys: PK (run_id, source_version_id)
Rules: The primary key allows one consolidated coverage row per (run, source revision). Store the actually searched/reviewed scope, not an inflated whole-document review claim.
## analysis.agent_outputs
A complete raw Agent A or Agent B JSON output and its schema-validation record.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| run_id | uuid | yes | The scoped review run to which this row belongs. |
| agent_role | text | yes | CURRENT_STATE for Agent A or ARTICLE_REVIEW for Agent B. |
| output_json | jsonb | yes | Complete saved message envelope and payload, without inventing fields outside the selected contract. |
| schema_validated | boolean | yes | Boolean validation marker retained alongside validation_status. A check requires it to agree with whether validation_status is VALID. |
| validation_details | jsonb | yes | Actual validator results and errors, including what contract/schema was used. JSONB alone does not validate the contract. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |
| contract_schema_sha256 | text | no | Fingerprint of the exact JSON Schema used for validation, when recorded. |
| validation_status | text | yes | NOT_VALIDATED, VALID or INVALID. The application must perform real JSON Schema validation before setting VALID. |
| model_details | jsonb | yes | Provider/model/configuration details for the agent call. |
| prompt_sha256 | text | no | Fingerprint of the exact prompt/instructions used for this output, when recorded. |

Keys: PK (id); UNIQUE (id, run_id)
Rules: schema_validated must equal (validation_status = VALID). Full contract validation is performed by the application, not by PostgreSQL JSONB shape checks.
## analysis.records
Individual observations or assessments extracted from a validated agent output, with their review and quality/currency states.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| run_id | uuid | yes | The scoped review run to which this row belongs. |
| agent_output_id | uuid | yes | Agent output containing this observation/assessment; the composite FK ensures it belongs to the same run. |
| record_key | text | yes | Original observation/assessment identifier from the output; unique within the run. |
| record_type | text | yes | OBSERVATION, ARTICLE_ASSESSMENT or FINDING. |
| subject_version_id | uuid | no | Optional primary logical source revision assessed by this record; supporting evidence can involve additional sources. |
| topic | text | yes | The specific topic being reviewed or described. |
| statement | text | yes | The derived observation, meaning or assessment text. It is separate from original evidence text. |
| evidence_level | text | no | Attributed evidence category/strength, such as visual, narrated or corroborated, as defined by the selected contract. |
| currency_status | text | no | MATCHES_RECORDED_SCOPE, UPDATE_REQUIRED, CONFLICTED or UNVERIFIED; scoped documentation currency, not universal product truth. |
| quality_status | text | no | ACCEPTABLE, IMPROVEMENT_NEEDED or INDETERMINATE; kept separate from documentation currency. |
| finding_type | text | no | Optional contract-defined finding category. Free text in the SQL; validate it against the active contract in the application. |
| review_status | text | yes | AGENT_PROPOSED, CONFIRMED, REJECTED or NEEDS_EVIDENCE. Confirmed/rejected promotion requires an attributed human-review row. |
| supersedes_record_id | uuid | no | Optional prior record replaced by this record; preserve history rather than silently overwriting its meaning. |
| details | jsonb | yes | Additional contract fields and scoped assessment details that do not have typed columns. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |

Keys: PK (id); UNIQUE (run_id, record_key)
Rules: The output/run composite FK prevents linking an output from a different run. A trigger requires a corresponding attributed human-review decision before CONFIRMED or REJECTED is assigned. A/B role semantics and B-to-A linking must also be checked by the application.
## analysis.record_evidence
A bridge connecting a derived record to original evidence, with an exact locator and quoted/observed excerpt.

| Field | Type | Required | Meaning |
|---|---|---|---|
| record_id | uuid | yes | The derived observation or assessment referenced by this row. |
| content_unit_id | uuid | yes | The original-evidence unit referenced by this row. |
| relationship | text | yes | SUPPORTS, CONTRADICTS or CONTEXT relationship between the derived record and this original-evidence unit. |
| locator | jsonb | yes | Exact cited position within the evidence unit/source, retained with the record citation. |
| excerpt | text | yes | Quoted text or explicitly described observation supporting the citation; do not manufacture an unavailable excerpt. |

Keys: PK (record_id, content_unit_id, relationship)
## analysis.record_links
A relationship between derived records, especially a B assessment referring to the A observation it assessed.

| Field | Type | Required | Meaning |
|---|---|---|---|
| from_record_id | uuid | yes | Record making the relationship, commonly a B assessment. |
| to_record_id | uuid | yes | Record being related to, commonly the A observation being assessed. Must differ from the source record. |
| relationship | text | yes | ASSESSES, SUPPORTS, CONTRADICTS or SUPERSEDES. Direction is from from_record_id to to_record_id. |

Keys: PK (from_record_id, to_record_id, relationship)
## analysis.human_reviews
An attributed human decision about an agent record. The application must authenticate the reviewer.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| record_id | uuid | yes | The derived observation or assessment referenced by this row. |
| reviewer_identity | text | yes | Real attributed human reviewer identifier. A nonblank string is required; authentication is the application's responsibility. |
| reviewed_at | timestamptz | yes | Actual time the human decision was made; not automatically filled from the row creation time. |
| decision | text | yes | CONFIRMED, REJECTED or NEEDS_EVIDENCE. |
| rationale | text | yes | Human explanation for the decision. |
| evidence_uri | text | yes | Reference to the human approval/rejection evidence or decision record. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |

Keys: PK (id)
Rules: The application must authenticate the reviewer and preserve the decision evidence. A nonblank name alone is not verified identity.
## retrieval.embedding_profiles
An immutable embedding model/configuration identity. A model, dimension or preprocessing change requires a new profile.

| Field | Type | Required | Meaning |
|---|---|---|---|
| id | uuid | yes | Database-generated UUID uniquely identifying this row. |
| profile_key | text | yes | Unique application name for this precise embedding configuration. |
| provider | text | yes | Embedding provider identifier. |
| model | text | yes | Embedding model identifier. |
| model_revision | text | yes | Model revision/version identifier used to avoid mixing incompatible generations. |
| dimensions | integer | yes | Vector length. Must be positive and no more than 16,000 in this draft; this storage bound is not a promise of ANN index support at every size. |
| distance_metric | text | yes | COSINE, L2 or INNER_PRODUCT. Retrieval must use the selected metric consistently. |
| preprocessing_version | text | yes | Version of the text preparation/chunk context rules used before embedding. |

Keys: PK (id); UNIQUE (profile_key)
Rules: An UPDATE trigger makes existing profiles immutable. Create a new profile when model/revision/dimensions/preprocessing/metric changes.
## retrieval.content_embeddings
A vector for one original-evidence unit under one embedding profile.

| Field | Type | Required | Meaning |
|---|---|---|---|
| content_unit_id | uuid | yes | The original-evidence unit referenced by this row. |
| profile_id | uuid | yes | The immutable embedding model/configuration used by this row. |
| input_sha256 | text | yes | SHA-256 of the exact UTF-8 embedded_text. A database check requires the stored hash and text to agree. |
| embedding | vector | yes | Numerical vector for the original-evidence unit. A trigger checks its dimensions against the profile. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |
| embedded_text | text | yes | Exact text sent to the embedding model, including any added heading/context, so the input is reproducible. |

Keys: PK (content_unit_id, profile_id)
Rules: One vector per (content_unit_id, profile_id). Exact input text/hash agreement and profile dimension matching are enforced; retrieval must still filter the correct model profile and source scope.
## retrieval.analysis_embeddings
A vector for one A/B analysis record under one embedding profile.

| Field | Type | Required | Meaning |
|---|---|---|---|
| record_id | uuid | yes | The derived observation or assessment referenced by this row. |
| profile_id | uuid | yes | The immutable embedding model/configuration used by this row. |
| input_sha256 | text | yes | SHA-256 of the exact UTF-8 embedded_text. A database check requires the stored hash and text to agree. |
| embedding | vector | yes | Numerical vector for the derived A/B record. A trigger checks its dimensions against the profile. |
| created_at | timestamptz | yes | Time this database row was created; defaults to the transaction timestamp. |
| embedded_text | text | yes | Exact analysis text/context sent to the embedding model. Do not confuse it with original source evidence. |

Keys: PK (record_id, profile_id)
Rules: One vector per (record_id, profile_id). Keep original evidence and A/B-derived findings distinguishable at retrieval time.
