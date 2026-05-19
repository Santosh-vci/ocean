import { useCallback, useEffect, useState } from "react";

import { fetchNextActions } from "../lib/api";
import type { NextActionResponse } from "../types/assistant";
import { useAssistantMode } from "./useAssistantMode";

type UseNextActionsOptions = {
  enabled?: boolean;
  objectType?: string;
  objectId?: string | number;
};

export function useNextActions(route: string, options: UseNextActionsOptions = {}) {
  const { mode, setMode } = useAssistantMode();
  const [data, setData] = useState<NextActionResponse | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshIndex, setRefreshIndex] = useState(0);
  const enabled = options.enabled ?? true;
  const objectType = options.objectType;
  const objectId = options.objectId;
  const refresh = useCallback(() => {
    setRefreshIndex((value) => value + 1);
  }, []);

  useEffect(() => {
    if (!enabled) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }

    if (mode === "off") {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetchNextActions({ route, mode, objectType, objectId })
      .then((response) => {
        if (!cancelled) {
          setData(response);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setData(null);
          setError(err instanceof Error ? err : new Error("Assistant unavailable"));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, mode, objectId, objectType, refreshIndex, route]);

  return { mode, setMode, data, error, loading, refresh };
}
