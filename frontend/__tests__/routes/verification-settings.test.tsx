import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SettingsService from "#/api/settings-service/settings-service.api";
import { MOCK_DEFAULT_USER_SETTINGS } from "#/mocks/handlers";
import VerificationSettingsScreen, {
  clientLoader,
} from "#/routes/verification-settings";
import { Settings } from "#/types/settings";

function buildSettings(overrides: Partial<Settings> = {}): Settings {
  return {
    ...MOCK_DEFAULT_USER_SETTINGS,
    ...overrides,
    conversation_settings: {
      ...MOCK_DEFAULT_USER_SETTINGS.conversation_settings,
      ...overrides.conversation_settings,
    },
    conversation_settings_schema:
      overrides.conversation_settings_schema ??
      MOCK_DEFAULT_USER_SETTINGS.conversation_settings_schema,
  };
}

function renderVerificationSettingsScreen() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });

  return render(<VerificationSettingsScreen />, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    ),
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("VerificationSettingsScreen", () => {
  it("keeps the confirmation controls visible in the basic view", async () => {
    vi.spyOn(SettingsService, "getSettings").mockResolvedValue(buildSettings());

    renderVerificationSettingsScreen();

    await screen.findByTestId("verification-settings-screen");

    expect(screen.getByTestId("confirmation-mode-toggle")).toBeInTheDocument();
  });

  it("does not reset hidden advanced verification fields when saving the basic view", async () => {
    const schema = structuredClone(
      MOCK_DEFAULT_USER_SETTINGS.conversation_settings_schema!,
    );
    const verificationSection = schema.sections.find(
      (section) => section.key === "verification",
    );

    if (!verificationSection) {
      throw new Error("Expected verification section in test schema");
    }

    verificationSection.fields.push({
      key: "verification.max_risk_score",
      label: "Max Risk Score",
      section: "verification",
      section_label: "Verification",
      value_type: "integer",
      default: 5,
      choices: [],
      depends_on: [],
      prominence: "major",
      secret: false,
      required: false,
    });

    vi.spyOn(SettingsService, "getSettings").mockResolvedValue(
      buildSettings({
        conversation_settings_schema: schema,
        conversation_settings: {
          ...MOCK_DEFAULT_USER_SETTINGS.conversation_settings,
          confirmation_mode: false,
          verification: {
            max_risk_score: 9,
          },
        },
      }),
    );
    const saveSettingsSpy = vi
      .spyOn(SettingsService, "saveSettings")
      .mockResolvedValue(true);

    renderVerificationSettingsScreen();

    await screen.findByTestId("verification-settings-screen");
    await userEvent.click(screen.getByTestId("confirmation-mode-toggle"));
    await userEvent.click(screen.getByTestId("save-button"));

    await waitFor(() => {
      expect(saveSettingsSpy).toHaveBeenCalledWith({
        conversation_settings: {
          confirmation_mode: true,
        },
      });
    });
  });
});

describe("clientLoader permission checks", () => {
  it("should export a clientLoader for route protection", () => {
    expect(clientLoader).toBeDefined();
    expect(typeof clientLoader).toBe("function");
  });
});
