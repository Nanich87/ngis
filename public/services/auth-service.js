'use strict';

let authService = (function () {

    function signIn(email, password) {
        if (firebase.auth().currentUser) {
            firebase.auth().signOut();
        } else {
            return firebase.auth().signInWithEmailAndPassword(email, password);
        }
    }

    function signUp(email, password) {
        return firebase.auth().createUserWithEmailAndPassword(email, password);
    }

    function sendEmailVerification() {
        firebase.auth().currentUser.sendEmailVerification().then(function () {
            alert('Email Verification Sent!');
        });
    }

    function sendPasswordReset(email) {
        firebase.auth().sendPasswordResetEmail(email).then(function () {
            alert('Password Reset Email Sent!');
        }).catch(function (error) {
            let errorCode = error.code;
            let errorMessage = error.message;

            if (errorCode == 'auth/invalid-email') {
                alert(errorMessage);
            } else if (errorCode == 'auth/user-not-found') {
                alert(errorMessage);
            }

            console.log(error);
        });
    }

    return {
        signIn: signIn,
        signUp: signUp,
        sendEmailVerification: sendEmailVerification,
        sendPasswordReset: sendPasswordReset
    };
}());