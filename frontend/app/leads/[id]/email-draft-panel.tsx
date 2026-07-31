"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost } from "@/lib/api";
import AutoAwesomeOutlinedIcon from "@mui/icons-material/AutoAwesomeOutlined";
import SaveOutlinedIcon from "@mui/icons-material/SaveOutlined";
import SendOutlinedIcon from "@mui/icons-material/SendOutlined";
import ThumbDownAltOutlinedIcon from "@mui/icons-material/ThumbDownAltOutlined";
import ThumbUpAltOutlinedIcon from "@mui/icons-material/ThumbUpAltOutlined";
import { Alert, Box, Button, Chip, LinearProgress, Stack, TextField, Typography } from "@mui/material";
import { PanelCard } from "../../ui";

type DraftResponse = {
  subject?: string;
  body?: string;
  message: string;
  attempt_count?: number;
  retry_reasons?: string[];
  guardrail_passed?: boolean;
  guardrail_issues?: string[];
  judge_score?: number;
  judge_status?: string;
  judge_reason?: string;
};

export default function EmailDraftPanel({
  leadId,
  initialSubject,
  initialBody,
  validationStatus,
  emailSentStatus
}: {
  leadId: number;
  initialSubject: string;
  initialBody: string;
  validationStatus: string;
  emailSentStatus: string;
}) {
  const router = useRouter();
  const [subject, setSubject] = useState(initialSubject);
  const [body, setBody] = useState(initialBody);
  const [status, setStatus] = useState("");
  const [review, setReview] = useState<DraftResponse | null>(null);
  const [humanReviewReason, setHumanReviewReason] = useState("");
  const [humanReviewAction, setHumanReviewAction] = useState("");
  const [loading, setLoading] = useState("");

  async function generate() {
    setLoading("generate");
    setStatus("");
    setHumanReviewAction("");
    try {
      const draft = await apiPost<DraftResponse>(`/${leadId}/generate-email`);
      setSubject(draft.subject || "");
      setBody(draft.body || "");
      setStatus(draft.message);
      setReview(draft);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Draft generation failed");
    } finally {
      setLoading("");
    }
  }

  async function save() {
    setLoading("save");
    setStatus("");
    setHumanReviewAction("");
    try {
      const draft = await apiPost<DraftResponse>(`/${leadId}/email-draft`, { subject, body });
      setStatus(draft.message);
      setReview(draft);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Draft save failed");
    } finally {
      setLoading("");
    }
  }

  async function send() {
    setLoading("send");
    setStatus("");
    try {
      const result = await apiPost<DraftResponse>(`/${leadId}/send-email-draft`, { subject, body });
      setStatus(result.message);
      setReview(result);
      router.refresh();
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Email send failed");
    } finally {
      setLoading("");
    }
  }

  async function recordFeedback(action: "approved" | "rejected") {
    const feedbackReason = humanReviewReason.trim();
    if (action === "rejected" && !feedbackReason) {
      setStatus("Please add the human rejection reason before saving this as an error example.");
      return;
    }

    setLoading(action);
    setStatus("");
    try {
      const result = await apiPost<DraftResponse>(`/${leadId}/email-feedback`, {
        action,
        subject,
        body,
        feedback:
          action === "approved"
            ? feedbackReason || "Human reviewer approved this draft."
            : `Human reviewer rejected this draft. Reason: ${feedbackReason}`,
        tone: "user_reviewed",
        campaign_type: ""
      });
      setStatus(result.message);
      setReview(result);
      setHumanReviewAction(action);
    } catch (err) {
      setStatus(err instanceof Error ? err.message : "Feedback save failed");
    } finally {
      setLoading("");
    }
  }

  const statusClass =
    status.toLowerCase().includes("failed") || status.toLowerCase().includes("only valid") ? "error" : "success";
  const emailAlreadySent = emailSentStatus === "sent";

  return (
    <PanelCard
      description="Generate, edit, approve, and send the initial email from one compact workspace."
      icon={<AutoAwesomeOutlinedIcon color="primary" />}
      title="Email Draft Review"
    >
      <Stack spacing={1.25}>
        {validationStatus !== "Valid" ? (
          <Alert severity="error">Only valid leads can receive emails. Current validation: {validationStatus}</Alert>
        ) : null}
        {emailAlreadySent ? (
          <Alert severity="success">Initial email has already been sent. Approval and rejection actions are locked.</Alert>
        ) : null}

        <Box component="form">
          <Stack spacing={1.15}>
            <TextField
              label="Subject"
              size="small"
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
            />
            <TextField
              label="Body"
              maxRows={7}
              minRows={5}
              multiline
              size="small"
              value={body}
              onChange={(event) => setBody(event.target.value)}
            />
            <Stack
              direction={{ xs: "column", md: "row" }}
              spacing={1}
              sx={{
                alignItems: { xs: "stretch", md: "center" },
                bgcolor: "#f8fafc",
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 2,
                flexWrap: "wrap",
                p: 1
              }}
            >
              <Button
                disabled={Boolean(loading)}
                onClick={(event) => {
                  event.preventDefault();
                  generate();
                }}
                startIcon={<AutoAwesomeOutlinedIcon />}
                variant="outlined"
              >
                {loading === "generate" ? "Generating..." : "Generate AI Email"}
              </Button>
              <Button
                disabled={Boolean(loading) || !subject || !body}
                onClick={(event) => {
                  event.preventDefault();
                  save();
                }}
                startIcon={<SaveOutlinedIcon />}
                variant="outlined"
              >
                {loading === "save" ? "Saving..." : "Save Draft"}
              </Button>
              <Button
                disabled={Boolean(loading) || validationStatus !== "Valid" || !subject || !body || emailAlreadySent}
                onClick={(event) => {
                  event.preventDefault();
                  send();
                }}
                startIcon={<SendOutlinedIcon />}
                variant="contained"
              >
                {emailAlreadySent ? "Email Sent" : loading === "send" ? "Sending..." : "Send Initial Email"}
              </Button>
              {!emailAlreadySent ? (
                <>
                  <Button
                    color="success"
                    disabled={Boolean(loading) || !subject || !body}
                    onClick={(event) => {
                      event.preventDefault();
                      recordFeedback("approved");
                    }}
                    startIcon={<ThumbUpAltOutlinedIcon />}
                    variant="outlined"
                  >
                    {loading === "approved" ? "Saving..." : "Approve Pattern"}
                  </Button>
                  <Button
                    color="error"
                    disabled={Boolean(loading) || !subject || !body}
                    onClick={(event) => {
                      event.preventDefault();
                      recordFeedback("rejected");
                    }}
                    startIcon={<ThumbDownAltOutlinedIcon />}
                    variant="outlined"
                  >
                    {loading === "rejected" ? "Saving..." : "Reject Draft"}
                  </Button>
                </>
              ) : null}
            </Stack>
            {!emailAlreadySent ? (
              <TextField
                helperText="Required for rejection. Optional note for approval."
                label="Human review reason"
                minRows={2}
                multiline
                onChange={(event) => setHumanReviewReason(event.target.value)}
                placeholder="Example: Tone is too generic, missing project location, CTA is weak..."
                size="small"
                value={humanReviewReason}
              />
            ) : null}
            {loading ? <LinearProgress /> : null}
          </Stack>
        </Box>

        {humanReviewAction ? (
          <Alert severity={humanReviewAction === "approved" ? "success" : "warning"}>
            Human review saved as {humanReviewAction === "approved" ? "gold example" : "error example"}.
          </Alert>
        ) : null}

        {review?.judge_status ? (
          <Alert severity={review.guardrail_passed && review.judge_status === "ready" ? "success" : "warning"} sx={{ py: 0.75 }}>
            <Stack spacing={0.75}>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                <Chip
                  label={review.guardrail_passed ? "Guardrails passed" : "Guardrails need review"}
                  size="small"
                  color={review.guardrail_passed ? "success" : "warning"}
                />
                <Chip label={`Judge: ${review.judge_status}`} size="small" />
                <Chip label={`Score: ${review.judge_score ?? 0}`} size="small" />
                {review.attempt_count ? <Chip label={`Attempts: ${review.attempt_count}`} size="small" /> : null}
              </Stack>
              <Typography variant="body2">{review.judge_reason}</Typography>
              {review.guardrail_issues?.length ? (
                <Typography variant="body2">{review.guardrail_issues.join(" ")}</Typography>
              ) : null}
              {review.retry_reasons?.length ? (
                <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
                  {review.retry_reasons.map((reason) => (
                    <Typography component="li" key={reason} variant="body2">
                      {reason}
                    </Typography>
                  ))}
                </Box>
              ) : null}
            </Stack>
          </Alert>
        ) : null}

        {status ? <Alert severity={statusClass === "error" ? "error" : "success"}>{status}</Alert> : null}
      </Stack>
    </PanelCard>
  );
}
