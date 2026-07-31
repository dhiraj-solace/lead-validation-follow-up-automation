"use client";

import ExpandMoreOutlinedIcon from "@mui/icons-material/ExpandMoreOutlined";
import MailOutlineOutlinedIcon from "@mui/icons-material/MailOutlineOutlined";
import { Accordion, AccordionDetails, AccordionSummary, Box, Chip, Stack, Typography } from "@mui/material";
import { EmptyState, PanelCard } from "../../ui";

type Message = {
  id: number;
  subject: string;
  body: string;
  status: string;
  direction: string;
  sent_at: string;
};

export default function ConversationHistory({ messages }: { messages: Message[] }) {
  return (
    <PanelCard icon={<MailOutlineOutlinedIcon color="primary" />} title="Conversation History">
      <Accordion
        disableGutters
        elevation={0}
        sx={{
          bgcolor: "transparent",
          border: "1px solid",
          borderColor: "divider",
          borderRadius: "12px !important",
          "&:before": { display: "none" }
        }}
      >
        <AccordionSummary expandIcon={<ExpandMoreOutlinedIcon />}>
          <Stack
            direction={{ xs: "column", sm: "row" }}
            spacing={1}
            sx={{ alignItems: { xs: "flex-start", sm: "center" }, width: "100%" }}
          >
            <Typography sx={{ fontWeight: 900 }}>Sent drafts and replies</Typography>
            <Chip label={`${messages.length} ${messages.length === 1 ? "Message" : "Messages"}`} size="small" />
          </Stack>
        </AccordionSummary>
        <AccordionDetails sx={{ pt: 0 }}>
          {messages.length ? (
            <Stack spacing={1}>
              {messages.map((message) => (
                <Box
                  key={message.id}
                  sx={{
                    bgcolor: "#f8fafc",
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 2,
                    p: 1.35
                  }}
                >
                  <Stack
                    direction={{ xs: "column", sm: "row" }}
                    spacing={0.75}
                    sx={{ alignItems: { xs: "flex-start", sm: "center" }, justifyContent: "space-between" }}
                  >
                    <Typography sx={{ fontSize: 15, fontWeight: 900 }}>
                      {message.subject || toTitleCase(message.direction)}
                    </Typography>
                    <Stack direction="row" spacing={0.75} sx={{ flexWrap: "wrap" }}>
                      <Chip label={toTitleCase(message.status)} size="small" sx={{ fontWeight: 800 }} />
                      <Chip label={formatDateTime(message.sent_at)} size="small" variant="outlined" />
                    </Stack>
                  </Stack>
                  <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                    {preview(message.body)}
                  </Typography>
                </Box>
              ))}
            </Stack>
          ) : (
            <EmptyState title="No messages yet" description="Generated and sent emails will appear here." />
          )}
        </AccordionDetails>
      </Accordion>
    </PanelCard>
  );
}

function preview(value?: string) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (!clean) {
    return "No preview available.";
  }
  return clean.length > 180 ? `${clean.slice(0, 180)}...` : clean;
}

function toTitleCase(value?: string | null) {
  const clean = String(value || "").replace(/[_-]+/g, " ").trim();
  if (!clean) {
    return "";
  }
  return clean
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "No date";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("en-IN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    year: "numeric"
  });
}
