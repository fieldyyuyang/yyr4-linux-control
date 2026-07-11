from dataclasses import dataclass

@dataclass(frozen=True)
class ObservationDiagnostics:
    discovery_attempts: int
    identities_selected: int
    streams_created: int
    raw_events_seen: int
    transport_source_events: int
    ignored_source_events: int
    control_events_emitted: int
    synthetic_releases_emitted: int
    normal_completions: int
    discovery_errors: int
    input_errors: int
    parser_errors: int
    cancellation_count: int
    reset_on_cancel_count: int
    dropped_synthetic_releases_on_cancel: int
    close_calls: int
