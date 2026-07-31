"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import WhatsAppIcon from "@mui/icons-material/WhatsApp";
import { Alert, Button, Stack, Typography } from "@mui/material";

export default function LeadActions({
  leadId,
  emailSentStatus,
  compact = false
}: {
  leadId: number;
  emailSentStatus: string;
  compact?: boolean;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState("");
  const [error, setError] = useState("");
  const initialEmailSent = emailSentStatus === "sent";

  async function sendFollowup() {
    setLoading("send");
    setError("");
    try {
      await apiPost(`/${leadId}/send-followup`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Follow-up send failed");
    } finally {
      setLoading("");
    }
  }

  async function markReplied() {
    setLoading("reply");
    setError("");
    try {
      await apiPost(`/${leadId}/mark-replied`, { reply_text: "Marked as replied from dashboard." });
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not mark the lead as replied");
    } finally {
      setLoading("");
    }
  }

  async function sendWhatsApp() {
    setLoading("whatsapp");
    setError("");
    try {
      await apiPost(`/${leadId}/send-whatsapp`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "WhatsApp send failed");
    } finally {
      setLoading("");
    }
  }

  return (
    <Stack spacing={1.25} sx={{ alignItems: "stretch" }}>
      {compact ? (
        <Stack spacing={0.4} sx={{ alignItems: "stretch" }}>
          <Typography color="text.secondary" variant="body2">
            Send a follow-up after the initial email, contact on WhatsApp, or stop automation when the lead replies.
          </Typography>
        </Stack>
      ) : null}
      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={1}
        sx={{
          alignItems: { xs: "stretch", sm: "center" },
          justifyContent: compact ? "flex-start" : "flex-end",
          flexWrap: "wrap",
          width: "100%"
        }}
      >
        {compact ? (
          <Button
            disabled={Boolean(loading) || !initialEmailSent}
            onClick={sendFollowup}
            startIcon={<SendOutlinedIcon />}
            sx={{ flex: compact ? "1 1 160px" : undefined, minWidth: { sm: 160 } }}
            variant="contained"
          >
            {loading === "send" ? "Sending..." : "Send Follow-Up"}
          </Button>
        ) : null}
        {compact ? (
          <Button
            disabled={Boolean(loading)}
            onClick={sendWhatsApp}
            startIcon={<WhatsAppIcon />}
            sx={{ flex: compact ? "1 1 160px" : undefined, minWidth: { sm: 160 } }}
            variant="outlined"
          >
            {loading === "whatsapp" ? "Sending..." : "Send WhatsApp"}
          </Button>
        ) : null}
        <Button
          disabled={Boolean(loading)}
          onClick={markReplied}
          startIcon={<CheckCircleOutlineOutlinedIcon />}
          sx={{ flex: compact ? "1 1 150px" : undefined, minWidth: { sm: compact ? 150 : 150 } }}
          variant="outlined"
        >
          {loading === "reply" ? "Saving..." : "Mark Replied"}
        </Button>
      </Stack>
      {!compact ? null : !initialEmailSent ? (
        <Alert severity="info" sx={{ py: 0.5 }}>
          Follow-up is enabled after the initial email is sent.
        </Alert>
      ) : null}
      {error ? <Alert severity="error">{error}</Alert> : null}
    </Stack>
  );
}
