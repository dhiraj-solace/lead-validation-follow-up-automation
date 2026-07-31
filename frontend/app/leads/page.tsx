import { apiGet, Lead } from "@/lib/api";
import Link from "next/link";
import ArrowForwardOutlinedIcon from "@mui/icons-material/ArrowForwardOutlined";
import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import ErrorOutlineOutlinedIcon from "@mui/icons-material/ErrorOutlineOutlined";
import FileUploadOutlinedIcon from "@mui/icons-material/FileUploadOutlined";
import LocalFireDepartmentOutlinedIcon from "@mui/icons-material/LocalFireDepartmentOutlined";
import PeopleAltOutlinedIcon from "@mui/icons-material/PeopleAltOutlined";
import {
  Box,
  Button,
  Card,
  CardActionArea,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { DraftStatusChip, EmailStatusChip, EmptyState, PageHeader, PanelCard, ScoreChip, ValidationChip } from "../ui";

export default async function LeadsPage() {
  const leads = await apiGet<Lead[]>("").catch(() => []);
  const totalLeads = leads.length;
  const validLeads = leads.filter((lead) => lead.validation_status === "Valid").length;
  const hotLeads = leads.filter((lead) => lead.score_band === "Hot").length;
  const invalidLeads = leads.filter((lead) => lead.validation_status === "Invalid").length;
  const sentEmails = leads.filter((lead) => lead.email_sent_status === "sent").length;
  const avgScore = totalLeads ? Math.round(leads.reduce((total, lead) => total + (lead.score || 0), 0) / totalLeads) : 0;
  const validPercent = totalLeads ? Math.round((validLeads / totalLeads) * 100) : 0;
  const sentPercent = totalLeads ? Math.round((sentEmails / totalLeads) * 100) : 0;

  return (
    <>
      <PageHeader
        action={
          <Button component={Link} href="/upload" startIcon={<FileUploadOutlinedIcon />} variant="contained">
            Upload Leads
          </Button>
        }
        description="Review contact quality, scoring, and email readiness across every imported lead."
        eyebrow="Leads"
        title="All imported leads"
      />

      <Grid container spacing={2} sx={{ mb: 2.5 }}>
        <Grid item xs={12} sm={6} lg={3}>
          <LeadStatCard
            icon={<PeopleAltOutlinedIcon />}
            label="Total leads"
            value={totalLeads}
            helper={`${avgScore} average score`}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <LeadStatCard
            accent="success"
            icon={<CheckCircleOutlineOutlinedIcon />}
            label="Valid leads"
            progress={validPercent}
            value={validLeads}
            helper={`${validPercent}% ready for outreach`}
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <LeadStatCard
            accent="warning"
            icon={<LocalFireDepartmentOutlinedIcon />}
            label="Hot leads"
            value={hotLeads}
            helper="Highest sales priority"
          />
        </Grid>
        <Grid item xs={12} sm={6} lg={3}>
          <LeadStatCard
            accent="error"
            icon={<ErrorOutlineOutlinedIcon />}
            label="Needs fix"
            progress={totalLeads ? Math.round((invalidLeads / totalLeads) * 100) : 0}
            value={invalidLeads}
            helper={`${sentPercent}% emails sent`}
          />
        </Grid>
      </Grid>

      <PanelCard
        action={
          leads.length ? (
            <Button component={Link} href="/high-priority" endIcon={<ArrowForwardOutlinedIcon />} variant="outlined">
              View priority
            </Button>
          ) : null
        }
        description={`${leads.length} imported leads sorted by latest import and current readiness.`}
        icon={<PeopleAltOutlinedIcon color="primary" />}
        title="Lead records"
      >
        {leads.length ? (
          <>
            <Paper
              elevation={0}
              sx={{
                alignItems: "center",
                bgcolor: "#f8fafc",
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 2,
                display: { xs: "none", md: "flex" },
                justifyContent: "space-between",
                mb: 2,
                px: 2,
                py: 1.5
              }}
            >
              <Stack direction="row" spacing={1} sx={{ alignItems: "center", flexWrap: "wrap" }}>
                <ValidationChip status="Valid" />
                <Typography color="text.secondary" variant="body2">
                  {validLeads} validated
                </Typography>
                <Divider flexItem orientation="vertical" />
                <ScoreChip band="Hot" />
                <Typography color="text.secondary" variant="body2">
                  {hotLeads} high priority
                </Typography>
                <Divider flexItem orientation="vertical" />
                <EmailStatusChip status="sent" />
                <Typography color="text.secondary" variant="body2">
                  {sentEmails} contacted
                </Typography>
              </Stack>
              <Typography color="text.secondary" variant="body2">
                Click any lead name to review draft, scoring, and actions
              </Typography>
            </Paper>

            <TableContainer
              sx={{
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 2.5,
                maxWidth: "100%",
                overflowX: "auto",
                overflowY: "hidden",
                WebkitOverflowScrolling: "touch"
              }}
            >
              <Table sx={{ minWidth: 1180, tableLayout: "fixed" }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 220 }}>Lead</TableCell>
                    <TableCell sx={{ width: 250 }}>Contact</TableCell>
                    <TableCell sx={{ width: 240 }}>Requirement</TableCell>
                    <TableCell sx={{ width: 300 }}>Validation</TableCell>
                    <TableCell sx={{ width: 120 }}>Score</TableCell>
                    <TableCell sx={{ width: 140 }}>Email</TableCell>
                    <TableCell align="right" sx={{ width: 130 }}>Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {leads.map((lead) => (
                    <TableRow
                      hover
                      key={lead.id}
                      sx={{
                        "&:last-child td": { borderBottom: 0 },
                        "&:hover": { bgcolor: "#f8fafc" }
                      }}
                    >
                      <TableCell>
                        <Stack spacing={0.5}>
                          <Link href={`/leads/${lead.id}`}>
                            <Typography component="span" sx={{ color: "primary.dark", fontWeight: 900 }}>
                              {lead.name}
                            </Typography>
                          </Link>
                          <Typography color="text.secondary" variant="body2">
                            {lead.source || "Unknown source"}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.35}>
                          <Typography sx={{ fontWeight: 700 }}>{lead.email || "-"}</Typography>
                          <Typography color="text.secondary" variant="body2">
                            {lead.phone || "-"}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.35}>
                          <Typography sx={{ fontWeight: 750 }}>{formatRequirement(lead)}</Typography>
                          <Typography color="text.secondary" variant="body2">
                            {lead.location_preference || "Any location"}
                          </Typography>
                          {lead.budget ? (
                            <Typography color="text.secondary" variant="caption">
                              Budget: {lead.budget}
                            </Typography>
                          ) : null}
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.75} sx={{ alignItems: "flex-start" }}>
                          <ValidationChip status={lead.validation_status || "Pending"} />
                          <Typography color="text.secondary" variant="body2">
                            {compactRemark(lead.validation_remarks)}
                          </Typography>
                          <Typography color="text.secondary" variant="caption">
                            Email {lead.email_status || "pending"} / Phone {lead.phone_status || "pending"}
                          </Typography>
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.75} sx={{ alignItems: "flex-start" }}>
                          <Typography sx={{ fontSize: 22, fontWeight: 900, lineHeight: 1 }}>{lead.score}</Typography>
                          <ScoreChip band={lead.score_band} />
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.75} sx={{ alignItems: "flex-start" }}>
                          <EmailStatusChip status={lead.email_sent_status} />
                          <DraftStatusChip ready={Boolean(lead.email_draft_subject)} />
                        </Stack>
                      </TableCell>
                      <TableCell align="right">
                        <Button
                          component={Link}
                          endIcon={<ArrowForwardOutlinedIcon />}
                          href={`/leads/${lead.id}`}
                          size="small"
                          variant="text"
                        >
                          Review
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>

            <Stack spacing={1.5} sx={{ display: "none" }}>
              {leads.map((lead) => (
                <Card key={lead.id} variant="outlined" sx={{ borderRadius: 2.5 }}>
                  <CardActionArea component={Link} href={`/leads/${lead.id}`} sx={{ p: 2 }}>
                    <Stack spacing={1.5}>
                      <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start", justifyContent: "space-between" }}>
                        <Box>
                          <Typography sx={{ fontWeight: 900 }}>{lead.name}</Typography>
                          <Typography color="text.secondary" variant="body2">
                            {lead.source || "Unknown source"}
                          </Typography>
                        </Box>
                        <Stack direction="row" spacing={0.75}>
                          <ValidationChip status={lead.validation_status || "Pending"} />
                          <ScoreChip band={lead.score_band} />
                        </Stack>
                      </Stack>

                      <Divider />

                      <Stack spacing={0.75}>
                        <LeadMobileLine label="Requirement" value={`${formatRequirement(lead)} in ${lead.location_preference || "any location"}`} />
                        <LeadMobileLine label="Contact" value={lead.email || lead.phone || "-"} />
                        <LeadMobileLine label="Score" value={`${lead.score} points`} />
                      </Stack>

                      <Stack direction="row" spacing={1} sx={{ alignItems: "center", justifyContent: "space-between" }}>
                        <Stack direction="row" spacing={0.75}>
                          <EmailStatusChip status={lead.email_sent_status} />
                          <DraftStatusChip ready={Boolean(lead.email_draft_subject)} />
                        </Stack>
                        <Typography color="primary.dark" sx={{ fontWeight: 850 }} variant="body2">
                          Review lead
                        </Typography>
                      </Stack>
                    </Stack>
                  </CardActionArea>
                </Card>
              ))}
            </Stack>
          </>
        ) : (
          <EmptyState title="No leads found" description="Upload a fixed-format CSV or Excel file to populate the lead list." />
        )}
      </PanelCard>
    </>
  );
}

function LeadStatCard({
  icon,
  label,
  value,
  helper,
  progress,
  accent = "primary"
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  helper: string;
  progress?: number;
  accent?: "primary" | "success" | "warning" | "error";
}) {
  const colors = {
    primary: { bg: "#e9f2ff", color: "#155ca8" },
    success: { bg: "#e5f7ef", color: "#0f7a55" },
    warning: { bg: "#fff3d7", color: "#946200" },
    error: { bg: "#fdecea", color: "#bf3b32" }
  };

  return (
    <Card sx={{ height: "100%" }}>
      <Stack spacing={1.5} sx={{ p: 2.25 }}>
        <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
          <Box
            sx={{
              alignItems: "center",
              bgcolor: colors[accent].bg,
              borderRadius: 2,
              color: colors[accent].color,
              display: "flex",
              height: 42,
              justifyContent: "center",
              width: 42
            }}
          >
            {icon}
          </Box>
          <Typography color="text.secondary" sx={{ fontSize: 12, fontWeight: 850, textTransform: "uppercase" }}>
            {label}
          </Typography>
        </Stack>
        <Box>
          <Typography sx={{ fontSize: 34, fontWeight: 950, lineHeight: 1 }}>{value}</Typography>
          <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
            {helper}
          </Typography>
        </Box>
        {typeof progress === "number" ? (
          <LinearProgress
            value={progress}
            variant="determinate"
            sx={{
              bgcolor: "#eef2f7",
              borderRadius: 99,
              height: 7,
              "& .MuiLinearProgress-bar": { bgcolor: colors[accent].color, borderRadius: 99 }
            }}
          />
        ) : null}
      </Stack>
    </Card>
  );
}

function LeadMobileLine({ label, value }: { label: string; value: string }) {
  return (
    <Stack direction="row" spacing={1.5} sx={{ justifyContent: "space-between" }}>
      <Typography color="text.secondary" variant="body2">
        {label}
      </Typography>
      <Typography sx={{ fontWeight: 750, textAlign: "right" }} variant="body2">
        {value}
      </Typography>
    </Stack>
  );
}

function formatRequirement(lead: Lead) {
  return [lead.configuration, lead.property_type].filter(Boolean).join(" ") || "Property requirement";
}

function compactRemark(value?: string) {
  if (!value) {
    return "No validation remarks";
  }
  return value.length > 88 ? `${value.slice(0, 88)}...` : value;
}
