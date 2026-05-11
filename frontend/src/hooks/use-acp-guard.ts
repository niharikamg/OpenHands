import { useEffect } from "react";
import { useNavigate } from "react-router";
import { useConfig } from "#/hooks/query/use-config";
import { useSettings } from "#/hooks/query/use-settings";
import { SettingsScope } from "#/types/settings";

/**
 * Redirect to ``/settings/agent`` when the personal-scope active agent is
 * ACP. Called by the LLM, condenser, and MCP personal-settings routes —
 * those screens have no useful content while an external ACP subprocess is
 * driving conversations.
 *
 * Org-scope variants of the same routes deliberately skip the redirect: org
 * admins still configure org-default LLM/condenser/MCP settings regardless
 * of any individual user's ACP choice. Callers in those routes should pass
 * the route's current ``scope`` and the hook will no-op for ``"org"``.
 *
 * Hooks can't be called conditionally, so the routes pass their scope in
 * and the hook short-circuits inside the effect rather than at the call
 * site.
 *
 * Gates on ``enable_acp`` too: if a user's ``agent_kind`` is ``"acp"`` but
 * an admin later flips ``ENABLE_ACP=false``, the ``/settings/agent`` target
 * itself bounces back to ``/settings``. Skipping the redirect here avoids
 * a one-frame redirect bounce in that case.
 */
export function useAcpGuardIfPersonal(scope: SettingsScope) {
  const navigate = useNavigate();
  const { data: config } = useConfig();
  // ACP active state is a *personal* setting; always read it from personal
  // scope so org-scope routes still get the correct answer when deciding
  // whether to redirect.
  const { data: personalSettings } = useSettings("personal");
  const isAcpEnabled = !!config?.feature_flags?.enable_acp;
  const isPersonalAcp =
    scope === "personal" &&
    isAcpEnabled &&
    personalSettings?.agent_settings?.agent_kind === "acp";

  useEffect(() => {
    if (isPersonalAcp) {
      navigate("/settings/agent", { replace: true });
    }
  }, [isPersonalAcp, navigate]);
}
