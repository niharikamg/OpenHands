import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AxiosError } from "axios";
import { useNavigate } from "react-router";
import { useSettings } from "#/hooks/query/use-settings";
import { useConfig } from "#/hooks/query/use-config";
import { useSaveSettings } from "#/hooks/mutation/use-save-settings";
import { SettingsDropdownInput } from "#/components/features/settings/settings-dropdown-input";
import { SettingsInput } from "#/components/features/settings/settings-input";
import { BrandButton } from "#/components/features/settings/brand-button";
import { Typography } from "#/ui/typography";
import { I18nKey } from "#/i18n/declaration";
import {
  displayErrorToast,
  displaySuccessToast,
} from "#/utils/custom-toast-handlers";
import { retrieveAxiosErrorMessage } from "#/utils/retrieve-axios-error-message";

export const handle = { hideTitle: true };

type AgentType = "openhands" | "acp";
type CommandPreset = "claude-code" | "codex" | "gemini-cli" | "custom";

const PRESET_COMMANDS: Record<Exclude<CommandPreset, "custom">, string> = {
  "claude-code": "npx -y @agentclientprotocol/claude-agent-acp",
  codex: "npx -y @zed-industries/codex-acp",
  "gemini-cli": "npx -y @google/gemini-cli --acp",
};

const COMMAND_PLACEHOLDER = PRESET_COMMANDS["claude-code"];

function tokenizeCommand(value: string): string[] {
  return value.split(/\s+/).filter(Boolean);
}

function detectPreset(text: string): CommandPreset {
  const trimmed = text.trim();
  for (const [key, cmd] of Object.entries(PRESET_COMMANDS)) {
    if (trimmed === cmd) return key as CommandPreset;
  }
  return "custom";
}

function AgentSettingsScreen() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { data: settings, isLoading } = useSettings();
  const { data: config, isLoading: isConfigLoading } = useConfig();
  const { mutate: saveSettings, isPending: isSaving } = useSaveSettings();

  const [agentType, setAgentType] = useState<AgentType>("openhands");
  const [commandText, setCommandText] = useState("");
  const [selectedPreset, setSelectedPreset] =
    useState<CommandPreset>("claude-code");
  const [acpModel, setAcpModel] = useState("");
  const [isDirty, setIsDirty] = useState(false);

  useEffect(() => {
    if (!settings) return;
    const kind = settings.agent_settings?.agent_kind;
    if (kind === "acp") {
      setAgentType("acp");

      const acpCommand = settings.agent_settings?.acp_command;
      const acpArgs = settings.agent_settings?.acp_args;
      const tokens: string[] = [
        ...(Array.isArray(acpCommand)
          ? acpCommand.filter((v): v is string => typeof v === "string")
          : []),
        ...(Array.isArray(acpArgs)
          ? acpArgs.filter((v): v is string => typeof v === "string")
          : []),
      ];
      const joined = tokens.join(" ");
      setCommandText(joined);
      setSelectedPreset(detectPreset(joined));

      const savedModel = settings.agent_settings?.acp_model;
      setAcpModel(typeof savedModel === "string" ? savedModel : "");
    } else {
      setAgentType("openhands");
      setCommandText("");
      setAcpModel("");
    }
    setIsDirty(false);
  }, [settings]);

  const isAcpEnabled = !!config?.feature_flags?.enable_acp;

  useEffect(() => {
    if (config && !isAcpEnabled) {
      navigate("/settings", { replace: true });
    }
  }, [config, isAcpEnabled, navigate]);

  if (isLoading || isConfigLoading || !isAcpEnabled) return null;

  const isAcp = agentType === "acp";
  const commandTokens = tokenizeCommand(commandText);
  const isAcpInvalid = isAcp && commandTokens.length === 0;

  const handleSave = () => {
    let agentSettingsDiff: Record<string, unknown>;
    if (isAcp) {
      agentSettingsDiff = {
        agent_kind: "acp",
        acp_server: "custom",
        acp_command: commandTokens,
        acp_args: [],
        acp_model: acpModel.trim() || null,
      };
    } else {
      agentSettingsDiff = {
        agent_kind: "openhands",
        acp_command: null,
        acp_args: null,
        acp_env: null,
        acp_model: null,
      };
    }

    saveSettings(
      { agent_settings_diff: agentSettingsDiff },
      {
        onError: (error) => {
          const message = retrieveAxiosErrorMessage(error as AxiosError);
          displayErrorToast(message || t(I18nKey.ERROR$GENERIC));
        },
        onSuccess: () => {
          displaySuccessToast(t(I18nKey.SETTINGS$SAVED));
          setIsDirty(false);
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-6 pb-8 max-w-2xl">
      <div>
        <Typography.H2 className="mb-2">
          {t(I18nKey.SETTINGS$AGENT)}
        </Typography.H2>
        <Typography.Paragraph className="text-sm text-[#A3A3A3]">
          {t(I18nKey.SETTINGS$AGENT_PAGE_DESCRIPTION)}
        </Typography.Paragraph>
      </div>

      <SettingsDropdownInput
        testId="agent-type-selector"
        name="agent-type"
        label={t(I18nKey.SETTINGS$AGENT)}
        items={[
          {
            key: "openhands",
            label: t(I18nKey.SETTINGS$AGENT_TYPE_OPENHANDS),
          },
          { key: "acp", label: t(I18nKey.SETTINGS$AGENT_TYPE_ACP) },
        ]}
        selectedKey={agentType}
        onSelectionChange={(key) => {
          if (!key) return;
          setAgentType(key as AgentType);
          setIsDirty(true);
        }}
      />

      {isAcp && (
        <>
          <SettingsDropdownInput
            testId="agent-preset-selector"
            name="agent-preset"
            label={t(I18nKey.SETTINGS$AGENT_PRESET)}
            items={[
              { key: "claude-code", label: "Claude Code" },
              { key: "codex", label: "Codex" },
              { key: "gemini-cli", label: "Gemini CLI" },
              {
                key: "custom",
                label: t(I18nKey.SETTINGS$AGENT_PRESET_CUSTOM),
              },
            ]}
            selectedKey={selectedPreset}
            onSelectionChange={(key) => {
              if (!key) return;
              const preset = key as CommandPreset;
              setSelectedPreset(preset);
              if (preset !== "custom") {
                setCommandText(PRESET_COMMANDS[preset]);
              }
              setIsDirty(true);
            }}
          />

          <div className="flex flex-col gap-2.5">
            <Typography.Text className="text-sm">
              {t(I18nKey.SETTINGS$MCP_COMMAND)}
            </Typography.Text>
            <textarea
              data-testid="agent-command-input"
              className="bg-tertiary border border-[#717888] rounded-sm p-2 text-sm font-mono text-white placeholder:italic placeholder:text-[#717888] min-h-[60px] resize-y focus:outline-none focus:border-white"
              value={commandText}
              placeholder={COMMAND_PLACEHOLDER}
              onChange={(e) => {
                const text = e.target.value;
                setCommandText(text);
                setSelectedPreset(detectPreset(text));
                setIsDirty(true);
              }}
            />
            <Typography.Text className="text-xs text-[#717888]">
              {t(I18nKey.SETTINGS$AGENT_COMMAND_HINT)}
            </Typography.Text>
          </div>

          <div className="flex flex-col gap-1.5">
            <SettingsInput
              testId="agent-model-input"
              label={t(I18nKey.SCHEMA$LLM$MODEL$LABEL)}
              type="text"
              className="w-full"
              value={acpModel}
              showOptionalTag
              onChange={(value) => {
                setAcpModel(value);
                setIsDirty(true);
              }}
            />
            <Typography.Text className="text-xs text-[#717888]">
              {t(I18nKey.SETTINGS$AGENT_MODEL_HINT)}
            </Typography.Text>
          </div>
        </>
      )}

      <div>
        <BrandButton
          testId="agent-save-button"
          type="button"
          variant="primary"
          isDisabled={isSaving || !isDirty || isAcpInvalid}
          onClick={handleSave}
        >
          {isSaving ? t(I18nKey.SETTINGS$SAVING) : t(I18nKey.BUTTON$SAVE)}
        </BrandButton>
      </div>
    </div>
  );
}

export default AgentSettingsScreen;
