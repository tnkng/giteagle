"""Tests for the activity aggregator."""

from datetime import datetime, timedelta

from giteagle.core.aggregator import ActivityAggregator
from giteagle.core.models import Activity, ActivityType, Repository


class TestActivityAggregator:
    """Tests for the ActivityAggregator class."""

    def test_add_activities(self, sample_activities):
        """Test adding activities to the aggregator."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        assert len(aggregator.activities) == len(sample_activities)

    def test_clear_activities(self, sample_activities):
        """Test clearing all activities."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)
        aggregator.clear()

        assert len(aggregator.activities) == 0

    def test_filter_by_activity_type(self, sample_activities):
        """Test filtering activities by type."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        commits = aggregator.filter(activity_types=[ActivityType.COMMIT])
        prs = aggregator.filter(activity_types=[ActivityType.PULL_REQUEST])
        issues = aggregator.filter(activity_types=[ActivityType.ISSUE])

        assert len(commits) == 5
        assert len(prs) == 3
        assert len(issues) == 2

    def test_filter_by_contributor(self, sample_activities):
        """Test filtering activities by contributor."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        # testuser has 5 commits + 2 issues = 7
        user_activities = aggregator.filter(contributors=["testuser"])
        assert len(user_activities) == 7

    def test_filter_by_date_range(self, sample_activities):
        """Test filtering activities by date range."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        now = datetime.now()
        # Get activities from the last 3 hours
        recent = aggregator.filter(since=now - timedelta(hours=3))

        # Should get first 3 commits (at hours 0, 1, 2)
        assert len(recent) == 3

    def test_filter_by_repository(self, multiple_repos, sample_contributor):
        """Test filtering activities by repository."""
        aggregator = ActivityAggregator()

        # Add activities for different repos
        now = datetime.now()
        for i, repo in enumerate(multiple_repos):
            for j in range(i + 1):  # repo-1: 1, repo-2: 2, repo-3: 3
                aggregator.add_activities(
                    [
                        Activity(
                            id=f"activity-{repo.name}-{j}",
                            type=ActivityType.COMMIT,
                            repository=repo,
                            contributor=sample_contributor,
                            timestamp=now - timedelta(hours=i * 10 + j),
                            title=f"Commit {j}",
                        )
                    ]
                )

        # Filter by first repo
        repo1_activities = aggregator.filter(repositories=[multiple_repos[0]])
        assert len(repo1_activities) == 1

        # Filter by third repo
        repo3_activities = aggregator.filter(repositories=[multiple_repos[2]])
        assert len(repo3_activities) == 3

    def test_filter_with_predicate(self, sample_activities):
        """Test filtering with custom predicate."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        # Filter for activities with "1" in the title
        filtered = aggregator.filter(predicate=lambda a: "1" in a.title)

        assert all("1" in a.title for a in filtered)

    def test_aggregate_returns_correct_counts(self, sample_activities):
        """Test that aggregate returns correct counts."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        result = aggregator.aggregate()

        assert result.total_count == 10
        assert result.by_type[ActivityType.COMMIT] == 5
        assert result.by_type[ActivityType.PULL_REQUEST] == 3
        assert result.by_type[ActivityType.ISSUE] == 2

    def test_aggregate_by_repository(self, multiple_repos, sample_contributor):
        """Test aggregation by repository."""
        aggregator = ActivityAggregator()
        now = datetime.now()

        # Add 2 activities for repo-1, 3 for repo-2
        for i in range(2):
            aggregator.add_activities(
                [
                    Activity(
                        id=f"r1-{i}",
                        type=ActivityType.COMMIT,
                        repository=multiple_repos[0],
                        contributor=sample_contributor,
                        timestamp=now - timedelta(hours=i),
                        title=f"Commit {i}",
                    )
                ]
            )

        for i in range(3):
            aggregator.add_activities(
                [
                    Activity(
                        id=f"r2-{i}",
                        type=ActivityType.COMMIT,
                        repository=multiple_repos[1],
                        contributor=sample_contributor,
                        timestamp=now - timedelta(hours=i),
                        title=f"Commit {i}",
                    )
                ]
            )

        result = aggregator.aggregate()

        assert result.by_repository["org1/repo-1"] == 2
        assert result.by_repository["org1/repo-2"] == 3

    def test_aggregate_by_contributor(self, sample_activities):
        """Test aggregation by contributor."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        result = aggregator.aggregate()

        # testuser has commits and issues
        assert result.by_contributor["testuser"] == 7
        # user0, user1, user2 each have 1 PR
        assert result.by_contributor["user0"] == 1
        assert result.by_contributor["user1"] == 1
        assert result.by_contributor["user2"] == 1

    def test_get_contributor_stats(self, sample_activities):
        """Test getting statistics for a specific contributor."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        stats = aggregator.get_contributor_stats("testuser")

        assert stats is not None
        assert stats.total_activities == 7
        assert stats.by_type[ActivityType.COMMIT] == 5
        assert stats.by_type[ActivityType.ISSUE] == 2
        assert stats.contributor.username == "testuser"

    def test_get_contributor_stats_nonexistent(self, sample_activities):
        """Test getting stats for a nonexistent contributor returns None."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        stats = aggregator.get_contributor_stats("nonexistent")

        assert stats is None

    def test_get_repository_stats(self, sample_repository, sample_activities):
        """Test getting statistics for a specific repository."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        stats = aggregator.get_repository_stats(sample_repository)

        assert stats is not None
        assert stats.total_activities == 10
        assert len(stats.contributors) == 4  # testuser + user0, user1, user2

    def test_get_activity_timeline_by_day(self, sample_contributor):
        """Test getting activity timeline by day."""
        aggregator = ActivityAggregator()
        now = datetime.now()

        repo = Repository(
            name="test-repo",
            owner="owner",
            platform="github",
            url="https://github.com/owner/test-repo",
        )

        # Add activities on different days
        for i in range(5):
            aggregator.add_activities(
                [
                    Activity(
                        id=f"activity-{i}",
                        type=ActivityType.COMMIT,
                        repository=repo,
                        contributor=sample_contributor,
                        timestamp=now - timedelta(days=i),
                        title=f"Commit {i}",
                    )
                ]
            )

        timeline = aggregator.get_activity_timeline(granularity="day")

        assert len(timeline) == 5
        assert all(count == 1 for count in timeline.values())

    def test_get_top_contributors(self, sample_activities):
        """Test getting top contributors."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        top = aggregator.get_top_contributors(limit=3)

        assert len(top) == 3
        assert top[0] == ("testuser", 7)  # Most active

    def test_get_most_active_repositories(self, multiple_repos, sample_contributor):
        """Test getting most active repositories."""
        aggregator = ActivityAggregator()
        now = datetime.now()

        # Add varying activities to each repo
        counts = [5, 3, 8]
        for repo, count in zip(multiple_repos, counts, strict=True):
            for i in range(count):
                aggregator.add_activities(
                    [
                        Activity(
                            id=f"{repo.name}-{i}",
                            type=ActivityType.COMMIT,
                            repository=repo,
                            contributor=sample_contributor,
                            timestamp=now - timedelta(hours=i),
                            title=f"Commit {i}",
                        )
                    ]
                )

        most_active = aggregator.get_most_active_repositories(limit=2)

        assert len(most_active) == 2
        assert most_active[0] == ("org2/repo-3", 8)
        assert most_active[1] == ("org1/repo-1", 5)

    def test_aggregate_date_range(self, sample_activities):
        """Test that aggregate returns correct date range."""
        aggregator = ActivityAggregator()
        aggregator.add_activities(sample_activities)

        result = aggregator.aggregate()

        assert result.date_range[0] is not None
        assert result.date_range[1] is not None
        assert result.date_range[0] <= result.date_range[1]

    def test_aggregate_empty(self):
        """Test aggregating with no activities."""
        aggregator = ActivityAggregator()
        result = aggregator.aggregate()

        assert result.total_count == 0
        assert len(result.by_repository) == 0
        assert len(result.by_contributor) == 0
        assert len(result.by_type) == 0
