/* A real macOS desktop launcher. The installer writes its private target into
 * Info.plist; no alias, shell, Terminal, browser, or developer runtime is used. */
#import <Cocoa/Cocoa.h>
#include <string.h>

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSString *path = [[NSBundle mainBundle] objectForInfoDictionaryKey:@"WorkbenchApplicationPath"];
        NSBundle *target = path ? [NSBundle bundleWithPath:path] : nil;
        BOOL valid = target && [[target bundleIdentifier] isEqualToString:@"org.volatilityworkbench.app"];
        if (argc == 2 && strcmp(argv[1], "--check-target") == 0) {
            if (valid) puts("Workbench application target verified");
            return valid ? 0 : 2;
        }
        [NSApplication sharedApplication];
        [NSApp setActivationPolicy:NSApplicationActivationPolicyAccessory];
        if (!valid) {
            NSAlert *alert = [[NSAlert alloc] init];
            alert.messageText = @"Volatility Workbench is unavailable";
            alert.informativeText = @"The installed application could not be found. Restore the previous application or reinstall Workbench and its desktop launcher.";
            [alert runModal];
            return 2;
        }
        NSWorkspaceOpenConfiguration *configuration = [NSWorkspaceOpenConfiguration configuration];
        configuration.activates = YES;
        configuration.createsNewApplicationInstance = NO;
        __block BOOL finished = NO;
        __block int result = 0;
        [[NSWorkspace sharedWorkspace] openApplicationAtURL:[NSURL fileURLWithPath:path]
            configuration:configuration completionHandler:^(NSRunningApplication *application, NSError *error) {
                dispatch_async(dispatch_get_main_queue(), ^{
                    if (error) {
                        NSAlert *alert = [[NSAlert alloc] init];
                        alert.messageText = @"Volatility Workbench could not open";
                        alert.informativeText = [error localizedDescription];
                        [alert runModal]; result = 1;
                    }
                    finished = YES;
                });
            }];
        NSDate *deadline = [NSDate dateWithTimeIntervalSinceNow:60];
        while (!finished && [deadline timeIntervalSinceNow] > 0) {
            [[NSRunLoop mainRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
        }
        return finished ? result : 3;
    }
}
