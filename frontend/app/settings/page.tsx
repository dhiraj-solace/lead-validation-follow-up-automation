import { API_BASE_URL } from "@/lib/api";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import CloudSyncOutlinedIcon from "@mui/icons-material/CloudSyncOutlined";
import DataObjectOutlinedIcon from "@mui/icons-material/DataObjectOutlined";
import FileUploadOutlinedIcon from "@mui/icons-material/FileUploadOutlined";
import { Box, Stack, Typography } from "@mui/material";
import { PageHeader, PanelCard } from "../ui";

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <Box
      sx={{
        borderTop: "1px solid",
        borderColor: "divider",
        display: "grid",
        gap: 1.5,
        gridTemplateColumns: { xs: "1fr", sm: "150px minmax(0, 1fr)" },
        p: 1.75,
        "&:first-of-type": {
          borderTop: 0
        }
      }}
    >
      <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography color="text.primary">{value}</Typography>
    </Box>
  );
}

function InlineCode({ children }: { children: React.ReactNode }) {
  return (
    <Box
      component="code"
      sx={{
        bgcolor: "#eef3f7",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 1,
        fontFamily: "monospace",
        fontSize: 12,
        px: 0.7,
        py: 0.2
      }}
    >
      {children}
    </Box>
  );
}

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        description="Confirm the frontend API target, upload schema, and service behavior for this local MVP."
        eyebrow="Settings"
        title="Runtime configuration"
      />

      <Box sx={{ display: "grid", gap: 2.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
        <PanelCard
          description="Next.js sends lead workflow requests to this backend endpoint."
          icon={<CloudSyncOutlinedIcon color="primary" />}
          title="Frontend API target"
        >
          <Box
            component="pre"
            sx={{
              bgcolor: "#0f172a",
              borderRadius: 2,
              color: "#e5edf7",
              fontFamily: "monospace",
              fontSize: 13,
              m: 0,
              overflowX: "auto",
              p: 2
            }}
          >
            {API_BASE_URL}
          </Box>
        </PanelCard>

        <PanelCard
          description="The importer expects fixed headers in row 1."
          icon={<FileUploadOutlinedIcon color="primary" />}
          title="Upload format"
        >
          <Box
            component="pre"
            sx={{
              bgcolor: "#0f172a",
              borderRadius: 2,
              color: "#e5edf7",
              fontFamily: "monospace",
              fontSize: 13,
              m: 0,
              overflowX: "auto",
              p: 2
            }}
          >
{`name
email
phone
source
property_type
configuration
location_preference
budget
timeline
message`}
          </Box>
        </PanelCard>

        <PanelCard
          description="Email and phone checks degrade gracefully when external keys are missing."
          icon={<DataObjectOutlinedIcon color="primary" />}
          title="Validation services"
        >
          <Stack sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
            <DetailRow label="Email" value="Format validation plus API deliverability when configured." />
            <DetailRow label="Phone" value="Format validation plus Twilio lookup when configured." />
            <DetailRow label="Fallback" value="Simple local validation keeps the upload flow usable." />
          </Stack>
        </PanelCard>

        <PanelCard
          description="OpenRouter generates drafts using lead context and saved templates."
          icon={<AutoAwesomeOutlinedIcon color="primary" />}
          title="AI email writer"
        >
          <Stack sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
            <DetailRow
              label="Provider"
              value={
                <>
                  OpenRouter when <InlineCode>OPENROUTER_API_KEY</InlineCode> is set in backend{" "}
                  <InlineCode>.env</InlineCode>.
                </>
              }
            />
            <DetailRow label="Fallback" value="Local demo writer creates a reviewable draft if the API is unavailable." />
            <DetailRow label="Sending" value="Reviewed drafts send through SMTP, or become demo-sent without SMTP." />
          </Stack>
        </PanelCard>
      </Box>
    </>
  );
}
