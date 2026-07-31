import { apiGet, Lead } from "@/lib/api";
import Link from "next/link";
import LocalFireDepartmentOutlinedIcon from "@mui/icons-material/LocalFireDepartmentOutlined";
import MailOutlineOutlinedIcon from "@mui/icons-material/MailOutlineOutlined";
import {
  Button,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { DraftStatusChip, EmailStatusChip, EmptyState, PageHeader, PanelCard, ScoreChip } from "../ui";

export default async function HighPriorityPage() {
  const leads = await apiGet<Lead[]>("/high-priority").catch(() => []);

  return (
    <>
      <PageHeader
        description="Focus on validated leads with the strongest budget, timeline, and requirement fit."
        eyebrow="High Priority"
        title="Valid hot leads"
      />

      <PanelCard
        description={`${leads.length} hot leads are currently ready for agent attention.`}
        icon={<LocalFireDepartmentOutlinedIcon color="secondary" />}
        title="Ready for outreach"
      >
        {leads.length ? (
          <TableContainer
            sx={{
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 2,
              maxWidth: "100%",
              overflowX: "auto",
              WebkitOverflowScrolling: "touch"
            }}
          >
            <Table sx={{ minWidth: 980, tableLayout: "fixed" }}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 250 }}>Lead</TableCell>
                  <TableCell sx={{ width: 260 }}>Requirement</TableCell>
                  <TableCell sx={{ width: 120 }}>Score</TableCell>
                  <TableCell sx={{ width: 170 }}>Agent</TableCell>
                  <TableCell sx={{ width: 150 }}>Email</TableCell>
                  <TableCell sx={{ width: 170 }}>Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {leads.map((lead) => (
                  <TableRow hover key={lead.id}>
                    <TableCell>
                      <Stack spacing={0.35}>
                        <Link href={`/leads/${lead.id}`}>
                          <Typography component="span" sx={{ fontWeight: 850 }}>
                            {lead.name}
                          </Typography>
                        </Link>
                        <Typography color="text.secondary" variant="body2">
                          {lead.email || "-"}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography>
                        {lead.configuration} {lead.property_type}
                      </Typography>
                      <Typography color="text.secondary" variant="body2">
                        {lead.location_preference || "Any location"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Stack spacing={0.75} sx={{ alignItems: "flex-start" }}>
                        <Typography>{lead.score}</Typography>
                        <ScoreChip band={lead.score_band} />
                      </Stack>
                    </TableCell>
                    <TableCell>{lead.assigned_agent_name || "Unassigned"}</TableCell>
                    <TableCell>
                      <Stack spacing={0.75} sx={{ alignItems: "flex-start" }}>
                        <EmailStatusChip status={lead.email_sent_status} />
                        <DraftStatusChip ready={Boolean(lead.email_draft_subject)} />
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Button
                        component={Link}
                        href={`/leads/${lead.id}`}
                        size="small"
                        startIcon={<MailOutlineOutlinedIcon />}
                        variant="outlined"
                      >
                        {lead.email_draft_subject ? "Review Draft" : "Write Email"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <EmptyState title="No hot leads right now" description="Validated leads with scores above 80 will appear here." />
        )}
      </PanelCard>
    </>
  );
}
