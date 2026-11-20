package com.gathin.tvhome;

import org.junit.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class ArtworkTaskTest {
    @Test public void deliversOnTheMainExecutor() {
        List<Runnable> main = new ArrayList<>();
        List<String> shown = new ArrayList<>();
        ArtworkTask<String> task = new ArtworkTask<>(() -> "banner", main::add, shown::add);
        task.run();
        assertTrue(shown.isEmpty());
        assertEquals(1, main.size());
        main.get(0).run();
        assertEquals("banner", shown.get(0));
    }

    @Test public void emptyArtworkIsDelivered() {
        List<String> shown = new ArrayList<>();
        new ArtworkTask<String>(() -> null, Runnable::run, shown::add).run();
        assertEquals(1, shown.size());
        assertEquals(null, shown.get(0));
    }

    @Test public void missingPackageDoesNotKillTheWorker() {
        List<String> shown = new ArrayList<>();
        new ArtworkTask<String>(() -> { throw new IllegalStateException("package removed"); },
                Runnable::run, shown::add).run();
        assertEquals(1, shown.size());
        assertEquals(null, shown.get(0));
        new ArtworkTask<>(() -> "next icon", Runnable::run, shown::add).run();
        assertEquals("next icon", shown.get(1));
    }

    @Test public void recyclingBeforeTheReadSkipsIt() {
        ArtworkTask<String> task = new ArtworkTask<>(() -> {
            throw new AssertionError("cancelled read");
        }, Runnable::run, value -> { throw new AssertionError("cancelled delivery"); });
        task.cancel();
        task.run();
    }

    @Test public void recyclingAfterTheReadRejectsStaleDelivery() {
        List<Runnable> main = new ArrayList<>();
        List<String> shown = new ArrayList<>();
        ArtworkTask<String> old = new ArtworkTask<>(() -> "old banner", main::add, shown::add);
        old.run();
        old.cancel();
        new ArtworkTask<>(() -> "new banner", main::add, shown::add).run();
        for (Runnable callback : main) callback.run();
        assertEquals(1, shown.size());
        assertEquals("new banner", shown.get(0));
    }

    @Test public void recyclingDuringTheReadSkipsDelivery() {
        List<Runnable> main = new ArrayList<>();
        List<ArtworkTask<String>> tasks = new ArrayList<>();
        ArtworkTask<String> task = new ArtworkTask<>(() -> {
            tasks.get(0).cancel();
            return "old icon";
        }, main::add, value -> { throw new AssertionError("cancelled delivery"); });
        tasks.add(task);
        task.run();
        assertTrue(main.isEmpty());
    }
}
