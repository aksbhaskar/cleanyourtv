package com.gathin.tvhome;

import java.util.concurrent.Executor;
import java.util.function.Consumer;
import java.util.function.Supplier;

/** A recycled tile can cancel both a queued read and its pending delivery. */
final class ArtworkTask<T> implements Runnable {
    private final Supplier<T> load;
    private final Executor main;
    private final Consumer<T> ready;
    private volatile boolean cancelled;

    ArtworkTask(Supplier<T> load, Executor main, Consumer<T> ready) {
        this.load = load;
        this.main = main;
        this.ready = ready;
    }

    void cancel() {
        cancelled = true;
    }

    @Override public void run() {
        if (cancelled) return;
        T result;
        try {
            result = load.get();
        } catch (RuntimeException ignored) {
            result = null;
        }
        final T value = result;
        if (!cancelled) main.execute(() -> {
            if (!cancelled) ready.accept(value);
        });
    }
}
